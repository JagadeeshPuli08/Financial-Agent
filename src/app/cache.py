import os
import pandas as pd
from collections import defaultdict
from dotenv import load_dotenv
from src.app.modals import UserProfile, UserProfileDateRange


load_dotenv()

class CacheManager:

    def _ensure_user_entry(self, user_id: str) -> dict:
        return cache.store.setdefault(
            user_id,
            {
                "profile": None,
                "query_history": [],
                "viz_state": [],
            },
        )

    def get_user_profile(self, user_id: str, df: pd.DataFrame) -> UserProfile | None:
        user_entry = self._ensure_user_entry(user_id)
        if user_entry["profile"] is not None:
            return user_entry["profile"]

        # computes the user profile
        user_transactions = df.loc[df["user_id"].astype(str) == user_id].copy()
        if user_transactions.empty:
            return None

        user_transactions["transaction_date"] = pd.to_datetime(
            user_transactions["transaction_date"], errors="raise"
        )
        user_transactions["transaction_amount"] = pd.to_numeric(
            user_transactions["transaction_amount"], errors="raise"
        )
        start_date = user_transactions["transaction_date"].min()
        end_date = user_transactions["transaction_date"].max()
        if pd.isna(start_date) or pd.isna(end_date):
            raise ValueError("User transactions must include valid transaction dates")

        months_in_range = (
            (end_date.year - start_date.year) * 12
            + end_date.month
            - start_date.month
            + 1
        )

        category_stats = (
            user_transactions.dropna(subset=["transaction_category_detail"])
            .groupby("transaction_category_detail", as_index=False)
            .agg(
                amount=("transaction_amount", "sum"),
                frequency=("transaction_category_detail", "size"),
            )
            .sort_values(
                ["amount", "frequency", "transaction_category_detail"],
                ascending=[False, False, True],
            )
        )
        merchant_stats = (
            user_transactions.dropna(subset=["merchant_name"])
            .groupby("merchant_name", as_index=False)
            .size()
            .sort_values(["size", "merchant_name"], ascending=[False, True])
        )
        user_names = user_transactions["user_name"].dropna()

        user_entry["profile"] = UserProfile(
            user_name=user_names.iloc[0] if not user_names.empty else "",
            transaction_count=len(user_transactions),
            date_range=UserProfileDateRange(
                start=start_date.date(),
                end=end_date.date(),
            ),
            top_categories=category_stats[
                "transaction_category_detail"
            ].head(3).tolist(),
            top_merchants=merchant_stats["merchant_name"].head(2).tolist(),
            average_monthly_spend=float(
                user_transactions["transaction_amount"].sum() / months_in_range
            ),
            dataset_version="v1",
        )
        return user_entry["profile"]

    def set_user_profile(self, user_id: str, df: pd.DataFrame):
        return self.get_user_profile(user_id, df)

    def get_query_history(self, user_id):
        if user_id in cache.store:
            return cache.store[user_id]["query_history"]
        return []

    def add_query_history(self, user_id, interaction):
        query_history = self._ensure_user_entry(user_id)["query_history"]
        max_history = int(os.getenv("LAST_N", "10"))
        if max_history < 1:
            raise ValueError("LAST_N must be a positive integer.")
        query_history.append(interaction)
        if len(query_history) > max_history:
            del query_history[:-max_history]
        return True

    def get_viz_state(self, user_id):
        if user_id in cache.store:
            return cache.store[user_id]["viz_state"]
        return []

    def set_viz_state(self, user_id, state):
        self._ensure_user_entry(user_id)["viz_state"] = state



class InMemoryCache:
    def __init__(self):
        self.store = defaultdict()

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)

cache = InMemoryCache()
cache_manager = CacheManager()