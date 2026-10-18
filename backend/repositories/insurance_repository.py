"""
InsuranceRepository: Insurance company CRUD and queries with agents.
"""
from config.database import get_db, row_to_dict, rows_to_list
from .base_repository import BaseRepository


class InsuranceRepository(BaseRepository):
    table_name = "insurance_companies"
    order_by = "company_name"

    def get_with_agents(self, iid: int) -> dict | None:
        """
        Get insurance company with its agents.
        """
        with get_db() as db:
            # Get insurance company
            company = db.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?",
                (iid,)
            ).fetchone()
            if not company:
                return None

            company = row_to_dict(company)

            # Get agents for this company
            agents = db.execute(
                """
                SELECT * FROM insurance_agents
                WHERE insurance_company_id = ?
                ORDER BY agent_name
                """,
                (iid,)
            ).fetchall()
            company["agents"] = rows_to_list(agents)

        return company

    def search_insurance(self, term: str, limit: int = 100) -> list[dict]:
        """
        Search insurance companies by company_name, contact_name, email, phone.
        """
        search_term = f"%{term}%"
        with get_db() as db:
            rows = db.execute(
                f"""
                SELECT * FROM {self.table_name}
                WHERE company_name LIKE ? OR contact_name LIKE ?
                   OR email LIKE ? OR phone LIKE ?
                ORDER BY {self.order_by}
                LIMIT ?
                """,
                (search_term, search_term, search_term, search_term, limit)
            ).fetchall()
        return rows_to_list(rows)
