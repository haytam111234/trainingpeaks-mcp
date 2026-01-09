"""TOOL-05: tp_get_peaks - Get personal records/peaks for a workout."""

from typing import Any

from tp_mcp.client import TPClient


async def _get_athlete_id(client: TPClient) -> int | None:
    """Get athlete ID from profile."""
    if client.athlete_id:
        return client.athlete_id

    response = await client.get("/users/v3/user")
    if response.success and response.data:
        # API returns nested structure: { user: { ... } }
        user_data = response.data.get("user", response.data)

        # Try personId first, then athletes array
        athlete_id = user_data.get("personId")
        if not athlete_id:
            athletes = user_data.get("athletes", [])
            if athletes:
                athlete_id = athletes[0].get("athleteId")

        client.athlete_id = athlete_id
        return athlete_id
    return None


async def tp_get_peaks(workout_id: str) -> dict[str, Any]:
    """Get personal records (peaks) for a specific workout.

    Args:
        workout_id: The workout ID to get PRs for.

    Returns:
        Dict with personal records including power and heart rate peaks.
    """
    async with TPClient() as client:
        athlete_id = await _get_athlete_id(client)
        if not athlete_id:
            return {
                "isError": True,
                "error_code": "AUTH_INVALID",
                "message": "Could not get athlete ID. Re-authenticate.",
            }

        endpoint = f"/personalrecord/v2/athletes/{athlete_id}/workouts/{workout_id}"
        params = {"displayPeaksForBasic": "true"}

        response = await client.get(endpoint, params=params)

        if response.is_error:
            return {
                "isError": True,
                "error_code": response.error_code.value if response.error_code else "API_ERROR",
                "message": response.message,
            }

        if not response.data:
            return {
                "workout_id": workout_id,
                "personal_record_count": 0,
                "records": [],
            }

        try:
            data = response.data
            records = data.get("personalRecords", [])

            # Group records by class (Power, HeartRate, etc.)
            power_records = []
            hr_records = []
            other_records = []

            for record in records:
                pr_class = record.get("class", "")
                pr_type = record.get("type", "")
                timeframe = record.get("timeFrame", {})

                formatted = {
                    "type": pr_type,
                    "value": record.get("value"),
                    "rank": record.get("rank"),
                    "timeframe": timeframe.get("name", ""),
                    "timeframe_start": timeframe.get("startDate", "").split("T")[0],
                    "timeframe_end": timeframe.get("endDate", "").split("T")[0],
                }

                if pr_class == "Power":
                    power_records.append(formatted)
                elif pr_class == "HeartRate":
                    hr_records.append(formatted)
                else:
                    formatted["class"] = pr_class
                    other_records.append(formatted)

            return {
                "workout_id": workout_id,
                "personal_record_count": data.get("personalRecordCount", len(records)),
                "power_records": power_records,
                "heart_rate_records": hr_records,
                "other_records": other_records if other_records else None,
            }

        except Exception as e:
            return {
                "isError": True,
                "error_code": "API_ERROR",
                "message": f"Failed to parse personal records: {e}",
            }
