# Fort Worth MyH2O

Home Assistant custom integration to fetch water usage from Fort Worth MyH2O portal.

Installation (HACS):
- Add this repository to HACS (Integrations) or install manually by copying the `custom_components/fort_worth_myh2o` folder to your HA `custom_components` directory.
- Restart Home Assistant.
- Configure the integration from Settings -> Devices & Services -> Add Integration -> Fort Worth MyH2O.

Notes:
- The integration scrapes the City portal. If the website layout changes the parser may need updates.
- The integration stores credentials in Home Assistant's config entries.
