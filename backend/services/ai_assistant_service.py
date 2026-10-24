import requests

try:
    from config import GROQ_API_KEY
except ImportError:
    try:
        from backend.config import GROQ_API_KEY
    except ImportError:
        GROQ_API_KEY = ""


class AIFarmAssistantService:
    def answer_farmer_query(self, 
                            query: str, 
                            farm_context: dict, 
                            custom_groq_key: str = "") -> str:
        """
        RAG-powered conversational assistant for farmers with current farm context awareness.
        """
        api_key = custom_groq_key or GROQ_API_KEY

        # Context summary
        farm_name = farm_context.get("farm_name", "My Farm")
        active_issues = farm_context.get("active_issues", [])
        weather = farm_context.get("weather", {})
        highest_priority = farm_context.get("highest_priority", None)

        context_str = f"Farm: {farm_name}. "
        if highest_priority:
            context_str += f"Highest Priority Issue: {highest_priority.get('issue_name')} (Tier: {highest_priority.get('priority_category')}, Score: {highest_priority.get('priority_score')}/100). "
        if active_issues:
            issues_list = ", ".join([i.get("issue_name", "") for i in active_issues])
            context_str += f"Active Issues: {issues_list}. "
        if weather:
            context_str += f"Current Weather: {weather.get('temperature')}°C, Humidity: {weather.get('humidity')}%, Rain Probability: {weather.get('rain_probability')}%, Condition: {weather.get('condition')}. "

        # Call Groq API if key present
        if api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                system_prompt = f"""
                You are the AI Farm Guardian Assistant — an expert agricultural advisor.
                You are helping a farmer with their specific farm data context:
                {context_str}
                Be concise, practical, empathetic, and actionable. Provide bullet points where relevant.
                Always ground recommendations in safety and local agricultural guidelines.
                """
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    "temperature": 0.5
                }
                res = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[AIAssistant] Groq Chat Assistant note: {e}")

        # Agronomic Rule-Based RAG Assistant Engine (Fallback)
        q_lower = query.lower()
        if "weather" in q_lower or "rain" in q_lower or "spray" in q_lower:
            rain_p = weather.get('rain_probability', 20)
            if rain_p >= 50:
                return f"🌧️ Weather Advisory: There is an elevated rain probability ({rain_p}%). We strongly recommend holding off chemical and fertilizer sprays to prevent product wash-off and toxic runoff into surrounding waterways."
            else:
                return f"☀️ Weather Advisory: Weather conditions are currently stable ({weather.get('temperature', 28)}°C, {weather.get('humidity', 70)}% humidity). Morning hours (06:30 - 09:30 AM) offer the best window for spraying with minimal drift."

        if "priority" in q_lower or "urgent" in q_lower or "risk" in q_lower:
            if highest_priority:
                return f"🚨 Highest Priority Notice: '{highest_priority.get('issue_name')}' is currently ranked {highest_priority.get('priority_category')} ({highest_priority.get('priority_score')}/100). Suggested action: deploy targeted treatment within 24 hours to prevent exponential spore propagation."
            return "✅ No critical priority alerts are active right now. All farm zones are performing within normal health thresholds."

        if "blast" in q_lower or "blight" in q_lower or "disease" in q_lower:
            return (
                "🌿 Disease Intervention Protocol:\n"
                "• Immediate Action: Prune infected lower canopy leaves with water-soaked lesions.\n"
                "• Bio-treatment: Foliar spray of Trichoderma viride or Neem Seed Kernel Extract (5%).\n"
                "• Chemical Intervention: Apply Tricyclazole 75% WP @ 0.6g/L or Azoxystrobin 23% SC @ 1 ml/L.\n"
                "• Safety Note: Maintain 24-hour field re-entry interval and wear proper PPE."
            )

        if "fertilizer" in q_lower or "nutrient" in q_lower:
            return (
                "🌱 Balanced Nutrition Protocol:\n"
                "• Avoid excessive nitrogen (urea) applications during disease flare-ups, as soft vegetative tissues accelerate fungal penetration.\n"
                "• Supplement with water-soluble 19:19:19 + chelated Zinc (Zn-EDTA 12% @ 1g/L) for rapid foliar vigor recovery."
            )

        return (
            f"Hello Farmer! I am your AI Farm Guardian Assistant. Based on your current farm context ({context_str}), "
            "I can help you prioritize field interventions, analyze weather risks for spraying, or provide customized treatment plans. "
            "How can I assist your crop management today?"
        )


ai_assistant_service = AIFarmAssistantService()
