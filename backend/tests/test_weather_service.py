import unittest
import sys
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import models
from database import Base
from routers import weather_router
from backend.services import weather_service


class WeatherServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        weather_service._weather_cache.clear()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.user = models.User(name="Weather User", email="weather@example.test", hashed_password="x")
        self.session.add(self.user)
        self.session.flush()
        self.farm = models.Farm(
            owner_id=self.user.id,
            name="Test farm",
            latitude=12.0,
            longitude=76.0,
        )
        self.session.add(self.farm)
        self.session.commit()

    def tearDown(self):
        weather_service._weather_cache.clear()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    async def test_force_refresh_fetches_current_openweather_values(self):
        requests = []

        def handler(request):
            requests.append(request.url.path)
            if request.url.path.endswith("/weather"):
                return httpx.Response(200, json={
                    "main": {"temp": 29.4, "feels_like": 31.0, "humidity": 71},
                    "wind": {"speed": 2.0},
                    "weather": [{"description": "clear sky", "icon": "01d"}],
                    "name": "Test location",
                    "timezone": 19800,
                })
            forecast_times = [
                ("2026-10-25 12:00:00", 0.4),
                ("2026-10-25 15:00:00", 0.6),
                ("2026-10-25 18:00:00", 0.8),
                ("2026-10-25 21:00:00", 0.2),
                ("2026-10-26 00:00:00", 0.3),
                ("2026-10-26 03:00:00", 0.4),
                ("2026-10-26 06:00:00", 0.5),
                ("2026-10-26 09:00:00", 0.6),
                ("2026-10-26 12:00:00", 0.7),
                ("2026-10-26 15:00:00", 0.8),
                ("2026-10-26 18:00:00", 0.9),
                ("2026-10-26 21:00:00", 0.4),
                ("2026-10-27 00:00:00", 0.3),
                ("2026-10-27 03:00:00", 0.2),
                ("2026-10-27 06:00:00", 0.1),
            ]
            return httpx.Response(200, json={
                "list": [{
                    "dt_txt": forecast_time,
                    "main": {"temp": 30.0, "humidity": 65},
                    "pop": rain_probability,
                } for forecast_time, rain_probability in forecast_times]
            })

        client_class = httpx.AsyncClient

        def create_client(**kwargs):
            return client_class(transport=httpx.MockTransport(handler), **kwargs)

        cached = {"temperature": 20.0, "source": "old cache"}
        weather_service._weather_cache[(12.3457, 76.5432)] = (10**12, cached)
        with patch.object(weather_service, "OPENWEATHER_API_KEY", "test-key"), patch.object(
            weather_service.httpx, "AsyncClient", side_effect=create_client
        ):
            result = await weather_service.get_weather(12.34567, 76.54321, force_refresh=True)

        assert result is not None
        self.assertEqual(result["temperature"], 29.4)
        self.assertEqual(result["rain_probability"], 40.0)
        self.assertEqual(result["timezone_offset"], 19800)
        self.assertEqual(
            [item["time"] for item in result["forecast"]],
            ["2026-10-25 12:00:00", "2026-10-26 06:00:00", "2026-10-27 06:00:00"],
        )
        self.assertEqual(result["source"], "OpenWeather")
        self.assertEqual(len(requests), 2)

    async def test_missing_api_key_returns_unavailable_not_fallback_values(self):
        with patch.object(weather_service, "OPENWEATHER_API_KEY", ""):
            result = await weather_service.get_weather(12.0, 76.0, force_refresh=True)

        self.assertIsNone(result)

    async def test_weather_endpoint_passes_manual_refresh_to_openweather_service(self):
        fresh_data = {"temperature": 28.0, "source": "OpenWeather"}
        with patch(
            "routers.weather_router.get_weather",
            new=AsyncMock(return_value=fresh_data),
        ) as get_weather:
            result = await weather_router.weather_for_farm(
                farm_id=cast(int, self.farm.id),
                refresh=True,
                db=self.session,
                user=self.user,
            )

        get_weather.assert_awaited_once_with(12.0, 76.0, force_refresh=True)
        self.assertTrue(result["connected"])
        self.assertEqual(result["data"], fresh_data)


if __name__ == "__main__":
    unittest.main()