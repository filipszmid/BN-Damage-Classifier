import pytest
import httpx
from loguru import logger

URL_SAVE_LABEL = 'http://localhost:8000/save-label/'
URL_DELETE_LABEL = 'http://localhost:8000/delete-label/'


@pytest.fixture
def labels_data():
    return [
        {
            "lokalizacja": "FB3N",
            "komponent": "PANEL",
            "rodzaj naprawy": "Straighten",
            "uszkodzenie": "Dent",
            "dlugosc": None,
            "szerokosc": None,
            "ilosc": 2,
            "godziny": "0.00",
            "material": "0.00",
            "wartosc": "0.00"
        },
        {
            "lokalizacja": "DB3N",
            "komponent": "HANDLE RETAINER",
            "rodzaj naprawy": "Straighten",
            "uszkodzenie": "Bent",
            "dlugosc": None,
            "szerokosc": None,
            "ilosc": 1,
            "godziny": "0.00",
            "material": "0.00",
            "wartosc": "0.00"
        },
        {
            "lokalizacja": "DB2N",
            "komponent": "HANDLE OT",
            "rodzaj naprawy": "Straighten",
            "uszkodzenie": "Bent",
            "dlugosc": None,
            "szerokosc": None,
            "ilosc": 1,
            "godziny": "0.25",
            "material": "0.00",
            "wartosc": "4.75"
        }
    ]

def test_save_and_delete_label(labels_data):
    pipeline_id = "11111111"
    response = httpx.post(URL_SAVE_LABEL + pipeline_id, json=labels_data, timeout=30.0)
    assert response.status_code == 200, "Failed to save labels, server responded with an error"
    result = response.json()
    logger.debug(result)
    assert "Labels saved successfully" in result['message'], "Labels were not saved successfully"
    print("Response from saving labels:", result)
    response = httpx.delete(URL_DELETE_LABEL + pipeline_id)
    assert response.status_code == 200
    assert f"File {pipeline_id}.json deleted successfully." in response.json()['message']
