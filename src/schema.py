from pydantic import BaseModel, Field


class LabelInfo(BaseModel):
    lokalizacja: str
    komponent: str
    rodzaj_naprawy: str = Field(alias="rodzaj naprawy")
    uszkodzenie: str
    dlugosc: float | None
    szerokosc: float | None
    ilosc: int
    godziny: str
    material: str
    wartosc: str
