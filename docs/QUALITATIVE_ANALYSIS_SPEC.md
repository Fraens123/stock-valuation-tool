# Geführte qualitative Unternehmensanalyse

## Ziel

Das neue Tool darf den Nutzer nicht nur durch Kennzahlen und eine DCF-Rechnung führen. Ein Kernwert des bestehenden Excel-Modells ist, dass man sich **mit dem Unternehmen beschäftigen muss**, bevor ein faires KGV oder ein Fair Value akzeptiert wird.

Deshalb wird Kapitel 5 des Buchs als eigener Analyseblock umgesetzt. Die Inhalte werden versioniert gespeichert und bei einer neuen Revision bewusst überprüft.

Maschinenlesbare Definitionen: `src/stock_valuation/knowledge/qualitative.yaml`.

---

## 1. Struktur nach Kindle-Ausgabe

- 5.1 Kompetenzbereich – Kindle 182
- 5.2 Charakteristika – 183
- 5.3 Rahmenbedingungen – 189
- 5.4 Informationsbeschaffung – 190
- 5.5 Branchenstrukturanalyse – 192
- 5.6 SWOT – 195
- 5.7 BCG – 197
- 5.8 Wettbewerbsstrategie – 205
- 5.9 Management – 206

Diese Struktur wird in der Anwendung als geführter Arbeitsablauf angezeigt.

---

## 2. Kein automatisches Punktesystem für Kapitel 5

Der normale Geschäftsmodellblock dient primär dem **Verstehen und Dokumentieren**. Nicht jede Antwort wird automatisch in Punkte übersetzt.

Pro Frage speichern wir:

- Antwort / Begründung
- optionale Einstufung
- Quelle(n)
- Stand der Quelle
- Datum der eigenen Einschätzung
- `not_applicable`, wenn der Punkt für das Unternehmen nicht sinnvoll ist

Bei einer neuen Analyse-Revision können die bisherigen Antworten übernommen werden, werden aber als **zu prüfen** markiert.

---

## 3. Zusammenhang mit dem fairen KGV

Die Multiplikatorenmethode verwendet im bestehenden Excel die Blöcke:

1. Sockel-KGV
2. Finanzielle Stabilität
3. Marktposition
4. Rentabilität
5. Wachstum
6. Individualität

Diese bleiben erhalten.

Die normalen Kapitel-5-Antworten dienen dabei als Evidenz. Beispiel:

- Kapitel 5 beschreibt die Kundenstruktur ausführlich.
- Im Fair-KGV-Block `Verhandlungsstärke der Abnehmer` wird daraus eine begründete Punkteentscheidung.

Damit soll die Punktevergabe **nicht isoliert und aus dem Bauch heraus** erfolgen.

---

## 4. Porter Five Forces

Das Excel enthält bereits fünf explizite Eingabepunkte:

- Rivalität bestehender Wettbewerber – `B605`
- neue Anbieter – `B610`
- Lieferantenmacht – `B615`
- Abnehmermacht – `B620`
- Ersatzprodukte – `B624`

Die neue UI zeigt pro Kraft:

- erklärenden `ⓘ`-Text
- qualitative Auswahl / Punkte gemäß später verifizierter Schmidlin-Skala
- eigene Begründung
- Quellen
- unterstützende Kennzahlen, wo sinnvoll

Beispiel für Rivalität:

Unterstützende Evidenz:
- EBIT-Marge
- Umsatzrendite
- Gesamtkapitalrendite
- Margenstabilität
- Marktanteile / Preissetzung

Die Software darf daraus später höchstens einen **Vorschlag** ableiten. Die endgültige qualitative Bewertung bleibt eine bewusste Nutzerentscheidung.

---

## 5. ASML als Referenzfall

Für ASML sollen in dieser Phase keine endgültigen Bewertungen vorweggenommen werden. Die Struktur muss aber folgende Themen aufnehmen können:

- technische Eintrittsbarrieren
- R&D-Intensität und Know-how
- Abhängigkeit von Speziallieferanten
- Kundenkonzentration
- technologische Substitution
- Exportkontrollen / Geopolitik
- installierte Basis / Serviceumsätze
- langfristige Halbleiternachfrage
- Kapitalbedarf und Kapazitätsausbau
- Management Guidance und langfristige Ziele

Diese Punkte zeigen, warum reine Kennzahlen für eine ASML-Bewertung nicht ausreichen.

---

## 6. Vergleich alter Analysen

Qualitative Änderungen sind im Revisionsvergleich ausdrücklich sichtbar.

Beispiel:

| Kriterium | alte Analyse | neue Analyse | Begründung |
|---|---|---|---|
| Abnehmermacht | gering | mittel | höhere Kundenkonzentration / veränderte Verhandlungssituation |
| geopolitisches Risiko | mittel | hoch | neue Exportrestriktionen |
| Management | sehr gut | gut | Guidance mehrfach verfehlt |

Diese Änderungshistorie ist Teil der Investmentakte und später auch im PDF-Report zusammenfassbar.

---

## 7. Offene Punkte

Vor Implementierung des endgültigen Fair-KGV-Scorings müssen die Kindle-Seiten ab 351 ff. gegen folgende Punkte geprüft werden:

- genaue Punkteskalen
- Sockel-KGV-Bandbreite
- Aufschlag finanzielle Stabilität
- mathematische Verknüpfung Marktposition × Rentabilität
- Wachstumsaufschläge
- Individualitätsaufschläge
- Definition der im Excel verwendeten ungehebelten Rendite/Quote

Bis dahin bleiben diese Werte konfigurierbar und werden nicht als fachlich endgültig festgeschrieben.
