import click
from pathlib import Path
from src.comparsion.pipeline import ComparisonPipeline
from loguru import logger

@click.command()
@click.option('--b24', type=click.Path(exists=True), required=True, help='Path to the B24 Report Excel file.')
@click.option('--sap', type=click.Path(exists=True), required=True, help='Path to the SAP Report Excel file.')
@click.option('--map', 'map_file', type=click.Path(exists=True), required=True, help='Path to the Mapping Excel file.')
@click.option('--out', type=click.Path(), default='comparison_output.xlsx', help='Path to save output Excel file.')
def main(b24, sap, map_file, out):
    """
    CLI tool to compare B24 and SAP reports using a mapping file.
    """
    logger.info("Starting comparison process...")
    pipeline = ComparisonPipeline(
        b24_path=b24,
        sap_path=sap,
        map_path=map_file,
        output_path=out
    )
    pipeline.run()

if __name__ == '__main__':
    main()
