from __future__ import annotations

from src.utils import compensation_band_for_jd


class MockHRISAdapter:
    def get_open_headcount(self) -> list[dict[str, object]]:
        return [
            {"department": "Engineering", "open_roles": 3},
            {"department": "Product", "open_roles": 1},
        ]

    def get_salary_band(self, role_title: str, location: str) -> dict[str, object]:
        low, high = compensation_band_for_jd({"role_title": role_title})
        return {"role_title": role_title, "location": location, "salary_min": low, "salary_max": high}

    def get_hiring_manager(self, role_id: int) -> dict[str, object]:
        return {"role_id": role_id, "name": "Demo Hiring Manager", "email": "manager@demo.local"}

    def get_department_policy(self, department: str) -> dict[str, object]:
        return {"department": department, "interview_sla_days": 5, "remote_policy": "remote-friendly"}

