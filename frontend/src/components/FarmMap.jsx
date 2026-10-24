import { useEffect } from 'react'
import {
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIconRetina from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

const defaultIcon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIconRetina,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
})

function ClickLocation({ onSelect }) {
  useMapEvents({
    click(event) {
      onSelect?.({ latitude: event.latlng.lat, longitude: event.latlng.lng })
    },
  })
  return null
}

function KeepMapCentered({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, zoom)
  }, [center, map, zoom])
  return null
}

export default function FarmMap({ farms = [], selectedLocation = null, onSelect = null }) {
  const firstSavedFarm = farms.find((farm) => farm.latitude != null && farm.longitude != null)
  if (!selectedLocation && !firstSavedFarm) {
    return (
      <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-gray-300 bg-gray-50 px-6 text-center">
        <p className="max-w-sm text-sm text-gray-600">
          No farm coordinates are recorded yet. Add coordinates or select a location on the map when creating a farm.
        </p>
      </div>
    )
  }
  const center = selectedLocation
    ? [selectedLocation.latitude, selectedLocation.longitude]
    : [firstSavedFarm.latitude, firstSavedFarm.longitude]
  const zoom = 11

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200">
      <MapContainer center={center} zoom={zoom} scrollWheelZoom className="h-72 w-full">
        <KeepMapCentered center={center} zoom={zoom} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickLocation onSelect={onSelect} />
        {farms.map((farm) => farm.latitude != null && farm.longitude != null && (
          <Marker
            key={`farm-${farm.id}`}
            position={[farm.latitude, farm.longitude]}
            icon={defaultIcon}
          >
            <Popup>
              <strong>{farm.name}</strong>
              <br />
              Farm · {farm.area_acres ?? 'Area not recorded'} acres
            </Popup>
          </Marker>
        ))}
        {farms.flatMap((farm) => (farm.fields || [])
          .filter((field) => field.latitude != null && field.longitude != null)
          .map((field) => (
            <Marker
              key={`field-${field.id}`}
              position={[field.latitude, field.longitude]}
              icon={defaultIcon}
            >
              <Popup>
                <strong>{field.name}</strong>
                <br />
                {field.crop} · {field.growth_stage || 'Stage not recorded'}
              </Popup>
            </Marker>
          )))}
        {selectedLocation && onSelect && (
          <Marker
            position={[selectedLocation.latitude, selectedLocation.longitude]}
            icon={defaultIcon}
          >
            <Popup>Selected location</Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  )
}
