# Projektübergreifende Verträge

Schnittstellen zu anderen Skytech-Projekten stehen hier. Die Struktur folgt den übrigen
Skytech-Repos:

```text
contract/
├── README.md
└── contract_<projektpaar>/
    ├── <vertragsdatei>
    └── <zugehörige Dokumente>   # falls vorhanden
```

Jedes Projektpaar besitzt einen eigenen Ordner. Der gemeinsame Vertrag liegt unter demselben
relativen Pfad in beiden beteiligten Repositories. Änderungen an der Schnittstelle werden im
selben Arbeitspaket in beiden Kopien nachgezogen. Lokale Doku verlinkt den Vertrag, statt eine
abweichende Beschreibung der gemeinsamen Felder zu führen.

## Verträge

| Gegenstelle | Vertrag | Master | Stand |
|---|---|---|---|
| Skytech X (Backend, Weboberfläche, iOS-App) | [contract_skytech_x_omniai/](contract_skytech_x_omniai/contract_skytech_x_omniai.md) | `Skytech-X-Backend/openapi/omniai-api-v1.yaml` | Version 1.2.0, in beiden Projekten implementiert |

## Regeln

- **Ordnername:** `contract_<master-besitzer>_<gegenstelle>`. Wer den Master besitzt, steht vorn,
  weil dort zuerst geändert wird (hier: Skytech-X-Backend → `contract_skytech_x_omniai`).

- **Der Master liegt beim Backend** (HTTP-Schnittstelle, OpenAPI). Hier liegt eine Kopie, die
  **wortgleich** bleibt — geändert wird zuerst im Master, dann wird die Kopie im
  selben Arbeitspaket nachgezogen.
- Änderungen innerhalb von `v1` bleiben additiv; ein Bruch bedeutet eine neue Hauptversion.
- Der Status im Vertragsdokument unterscheidet implementierten Austausch, bekannte Grenzen und
  Entwürfe. Ein Plan oder eine Doku-Änderung allein implementiert keine Schnittstelle.
- Der Abgleich der Kopie mit dem Master ist noch Handarbeit; eine prüfende CI-Stufe ist als
  Option in der Vorlage vorgeschlagen, aber nicht entschieden.
