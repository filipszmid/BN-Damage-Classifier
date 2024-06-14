# Report Damage Classifier
App which identifies damages listed on reports.
## Quickstart:
1. Set the .env:
```
OPENAI_API_KEY=
GOOGLE_APPLICATION_CREDENTIALS=
```
2. Within first run need OCR to authenticate to create GCP token.
3. Build image: ```make build```
4. Run REST API ```make up```
5. Install developer venv ```make venv```
5. Run integration tests: ```make test```

Logs are created in **logs/** directory.  

In **data/price_catalogues** there need to be:
* Zakres L1;Typ - Komponent.xlsx
* excel_3269.xlsx

Swagger and testing the endpoints:
http://0.0.0.0:8000/docs