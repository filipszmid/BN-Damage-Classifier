import pandas as pd
from loguru import logger

from src.config import get_config


class PricerWorkflow:
    """
    Class to manage the pricing workflow, including filtering and aggregating component data.

    Attributes:
        components_map (pd.DataFrame): DataFrame containing component mappings.
        pricer (pd.DataFrame): DataFrame containing pricing data.
    """

    def __init__(self):
        """Initialize the PricerWorkflow with configuration settings and load necessary data."""
        config = get_config()
        self.components_map = pd.read_excel(
            config["paths"]["pricer"]["components_map_path"]
        )
        self.pricer = pd.read_excel(config["paths"]["pricer"]["pricer_path"])

    def filter_component_map(
        self, l1_values: list, container_type: str
    ) -> pd.DataFrame:
        """
        Filter the component map based on the 'L1' and 'Typ' columns.

        Parameters:
            l1_values (list): List of values to filter by in the 'L1' column.
            container_type (str): The type of container to filter by in the 'Typ' column.

        Returns:
            pd.DataFrame: A DataFrame filtered and sorted by 'L1', 'Typ', and 'Komponent' columns.
        """
        filtered_df = self.components_map[
            self.components_map["L1"].isin(l1_values)
            & (self.components_map["Typ"] == container_type)
        ]
        return filtered_df.sort_values(by=["L1", "Typ", "Komponent"])

    def filter_based_on_price_list(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter the pricing data based on matches found in a given DataFrame.

        Parameters:
            df (pd.DataFrame): DataFrame with filtered components.

        Returns:
            pd.DataFrame: DataFrame filtered and sorted by 'ISO Ściana', 'Typ', 'Komponent PL', 'Operacja PL'.
        """
        filtered_df = self.pricer[
            (self.pricer["ISO Ściana"].isin(df["L1"]))
            & (self.pricer["Typ"].isin(df["Typ"]))
            & (self.pricer["Komponent PL"].isin(df["Komponent"]))
        ]
        operations = filtered_df[["ISO Ściana", "Typ", "Komponent PL", "Operacja PL"]]
        return (
            operations.drop_duplicates()
            .sort_values(by=["ISO Ściana", "Typ", "Komponent PL", "Operacja PL"])
            .reset_index(drop=True)
        )

    @staticmethod
    def aggregate_by_components(df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate data by components, collecting operations into lists.

        Parameters:
            df (pd.DataFrame): DataFrame with operations data.

        Returns:
            pd.DataFrame: Aggregated DataFrame by 'ISO Ściana', 'Typ', 'Komponent PL'.
        """
        return (
            df.groupby(["ISO Ściana", "Typ", "Komponent PL"])["Operacja PL"]
            .agg(list_of_possible_operations=lambda x: list(x.unique()))
            .reset_index()
        )

    @staticmethod
    def parse_to_hints(df: pd.DataFrame) -> pd.DataFrame:
        """
        Modify the DataFrame to prepare hints by renaming and dropping columns.

        Parameters:
            df (pd.DataFrame): The DataFrame to modify.

        Returns:
            pd.DataFrame: DataFrame with renamed and dropped columns.
        """
        df = df.rename(
            columns={"ISO Ściana": "special_code_letter_1", "Komponent PL": "component"}
        )
        return df.drop(columns=["Typ"])

    def get_pricing_data(
        self, letter_1_list: list, container_type: str
    ) -> pd.DataFrame:
        """
        Retrieve processed and formatted pricing data based on specified criteria.

        Parameters:
            letter_1_list (list): List of 'L1' values to filter components.
            container_type (str): Container type to filter components.

        Returns:
            pd.DataFrame: DataFrame containing the final processed and aggregated pricing data.
        """
        components = self.filter_component_map(letter_1_list, container_type)
        operations = self.filter_based_on_price_list(components)
        aggregates = self.aggregate_by_components(operations)
        return self.parse_to_hints(aggregates)


if __name__ == "__main__":
    pricer = PricerWorkflow()
    l1_list, con_type = ["D", "F"], "DC"
    logger.debug(
        f"Starting pricing workflow for L1: {l1_list} and container type: {con_type}"
    )
    final_data = pricer.get_pricing_data(l1_list, con_type)
    logger.debug(final_data)
