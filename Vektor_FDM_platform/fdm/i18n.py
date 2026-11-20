"""Traduções da plataforma e do relatório: português, inglês, francês e espanhol.

Uso: t("key", lang, **valores). Chave em falta num idioma cai para inglês e depois para português.
Os nomes dos eventos ficam como no programa FDM do operador (normalmente em inglês).
"""
from __future__ import annotations

LANGS = {"pt": "Português", "en": "English", "fr": "Français", "es": "Español"}
DEFAULT = "pt"

PHASES = {
    "pt": {"GROUND": "Solo", "TAXI_OUT": "Táxi de saída", "TAKEOFF": "Descolagem", "INITIAL_CLIMB": "Subida inicial",
           "CLIMB": "Subida", "CRUISE": "Cruzeiro", "DESCENT": "Descida", "APPROACH": "Aproximação",
           "LANDING": "Aterragem", "TAXI_IN": "Táxi de chegada", "GO_AROUND": "Borrego"},
    "en": {"GROUND": "Ground", "TAXI_OUT": "Taxi out", "TAKEOFF": "Take-off", "INITIAL_CLIMB": "Initial climb",
           "CLIMB": "Climb", "CRUISE": "Cruise", "DESCENT": "Descent", "APPROACH": "Approach",
           "LANDING": "Landing", "TAXI_IN": "Taxi in", "GO_AROUND": "Go-around"},
    "fr": {"GROUND": "Sol", "TAXI_OUT": "Roulage départ", "TAKEOFF": "Décollage", "INITIAL_CLIMB": "Montée initiale",
           "CLIMB": "Montée", "CRUISE": "Croisière", "DESCENT": "Descente", "APPROACH": "Approche",
           "LANDING": "Atterrissage", "TAXI_IN": "Roulage arrivée", "GO_AROUND": "Remise des gaz"},
    "es": {"GROUND": "Tierra", "TAXI_OUT": "Rodaje de salida", "TAKEOFF": "Despegue", "INITIAL_CLIMB": "Ascenso inicial",
           "CLIMB": "Ascenso", "CRUISE": "Crucero", "DESCENT": "Descenso", "APPROACH": "Aproximación",
           "LANDING": "Aterrizaje", "TAXI_IN": "Rodaje de llegada", "GO_AROUND": "Motor y al aire"},
}

LEVELS = {
    "pt": {0: "Normal", 1: "Nível 1 · Baixo", 2: "Nível 2 · Médio", 3: "Nível 3 · Alto"},
    "en": {0: "Normal", 1: "Level 1 · Low", 2: "Level 2 · Medium", 3: "Level 3 · High"},
    "fr": {0: "Normal", 1: "Niveau 1 · Faible", 2: "Niveau 2 · Moyen", 3: "Niveau 3 · Élevé"},
    "es": {0: "Normal", 1: "Nivel 1 · Bajo", 2: "Nivel 2 · Medio", 3: "Nivel 3 · Alto"},
}

S: dict[str, dict[str, str]] = {
    # ---------------- Relatório ----------------
    "rep_title": {"pt": "Relatório de Análise de Voo", "en": "Flight Analysis Report",
                  "fr": "Rapport d'analyse de vol", "es": "Informe de análisis de vuelo"},
    "rep_band": {"pt": "Relatório de Flight Data Monitoring", "en": "Flight Data Monitoring Report",
                 "fr": "Rapport Flight Data Monitoring", "es": "Informe de Flight Data Monitoring"},
    "rep_conf": {"pt": "CONFIDENCIAL · Dados desidentificados", "en": "CONFIDENTIAL · De-identified data",
                 "fr": "CONFIDENTIEL · Données désidentifiées", "es": "CONFIDENCIAL · Datos desidentificados"},
    "rep_footer": {"pt": "Uso exclusivo para fins de segurança operacional (SMS). Não utilizar para fins disciplinares.",
                   "en": "For safety management (SMS) purposes only. Not to be used for disciplinary purposes.",
                   "fr": "Usage exclusif à des fins de sécurité (SGS). Ne pas utiliser à des fins disciplinaires.",
                   "es": "Uso exclusivo para fines de seguridad operacional (SMS). No utilizar con fines disciplinarios."},
    "page": {"pt": "Página", "en": "Page", "fr": "Page", "es": "Página"},
    "flight": {"pt": "Voo", "en": "Flight", "fr": "Vol", "es": "Vuelo"},
    "generated": {"pt": "Gerado em {d} · Perfil de análise: {p}", "en": "Generated {d} · Analysis profile: {p}",
                  "fr": "Généré le {d} · Profil d'analyse : {p}", "es": "Generado el {d} · Perfil de análisis: {p}"},
    "seg_of": {"pt": "Voo {i} de {n} no download", "en": "Flight {i} of {n} in the download",
               "fr": "Vol {i} sur {n} dans le téléchargement", "es": "Vuelo {i} de {n} en la descarga"},
    "warn_layout": {
        "pt": "<b>Mapeamento de parâmetros provisório.</b> Os parâmetros deste relatório foram identificados por engenharia "
              "inversa (coerência física com a trajetória) e não foram validados contra o Data Frame Layout oficial. Os eventos "
              "servem para demonstração e triagem; não devem ser usados para decisões operacionais nem comunicados à "
              "tripulação antes da validação. Ver anexo A.",
        "en": "<b>Provisional parameter mapping.</b> The parameters in this report were identified by reverse engineering "
              "(physical consistency with the flight path) and have not been validated against the official Data Frame "
              "Layout. Events are for demonstration and screening only; do not use them for operational decisions or crew "
              "contact before validation. See Annex A.",
        "fr": "<b>Correspondance des paramètres provisoire.</b> Les paramètres de ce rapport ont été identifiés par rétro-"
              "ingénierie (cohérence physique avec la trajectoire) et n'ont pas été validés par rapport au Data Frame Layout "
              "officiel. Les événements servent à la démonstration et au tri ; ne pas les utiliser pour des décisions "
              "opérationnelles ni les communiquer à l'équipage avant validation. Voir l'annexe A.",
        "es": "<b>Mapeo de parámetros provisional.</b> Los parámetros de este informe se identificaron por ingeniería inversa "
              "(coherencia física con la trayectoria) y no se han validado frente al Data Frame Layout oficial. Los eventos "
              "sirven para demostración y cribado; no deben usarse para decisiones operativas ni comunicarse a la "
              "tripulación antes de la validación. Ver anexo A."},
    "kpi_max": {"pt": "Risco máximo do voo", "en": "Highest flight risk", "fr": "Risque maximal du vol", "es": "Riesgo máximo del vuelo"},
    "kpi_events": {"pt": "Eventos detetados", "en": "Events detected", "fr": "Événements détectés", "es": "Eventos detectados"},
    "kpi_index": {"pt": "Índice de risco (1·N1 + 4·N2 + 9·N3)", "en": "Risk index (1·L1 + 4·L2 + 9·L3)",
                  "fr": "Indice de risque (1·N1 + 4·N2 + 9·N3)", "es": "Índice de riesgo (1·N1 + 4·N2 + 9·N3)"},
    "kpi_air": {"pt": "Tempo de voo (ar)", "en": "Airborne time", "fr": "Temps de vol", "es": "Tiempo de vuelo"},
    "kpi_sync": {"pt": "Qualidade de sincronismo", "en": "Sync quality", "fr": "Qualité de synchronisation", "es": "Calidad de sincronismo"},
    "s1": {"pt": "1. Síntese", "en": "1. Summary", "fr": "1. Synthèse", "es": "1. Síntesis"},
    "sum_events": {
        "pt": "Foram descodificados {np} parâmetros ao longo de {dur} de gravação e avaliados {nav} dos {nt} eventos do programa. "
              "O voo registou {ne} evento(s): {c3} de nível 3, {c2} de nível 2 e {c1} de nível 1. O evento mais relevante foi "
              "<b>{top}</b> na fase de {phase}, com pico de {peak} {u} face a um limiar de nível {lvl} de {th} {u}. As ações de "
              "mitigação recomendadas encontram-se na secção 4 e devem ser validadas pelo Safety Manager antes da implementação.",
        "en": "{np} parameters were decoded over {dur} of recording and {nav} of the {nt} programme events were evaluated. "
              "The flight recorded {ne} event(s): {c3} level 3, {c2} level 2 and {c1} level 1. The most relevant event was "
              "<b>{top}</b> during {phase}, peaking at {peak} {u} against a level {lvl} threshold of {th} {u}. Recommended "
              "mitigation actions are in section 4 and must be validated by the Safety Manager before implementation.",
        "fr": "{np} paramètres ont été décodés sur {dur} d'enregistrement et {nav} des {nt} événements du programme ont été "
              "évalués. Le vol a enregistré {ne} événement(s) : {c3} de niveau 3, {c2} de niveau 2 et {c1} de niveau 1. "
              "L'événement le plus significatif est <b>{top}</b> en phase {phase}, avec un pic de {peak} {u} pour un seuil "
              "de niveau {lvl} de {th} {u}. Les actions d'atténuation recommandées figurent en section 4 et doivent être "
              "validées par le Safety Manager avant leur mise en œuvre.",
        "es": "Se decodificaron {np} parámetros a lo largo de {dur} de grabación y se evaluaron {nav} de los {nt} eventos del "
              "programa. El vuelo registró {ne} evento(s): {c3} de nivel 3, {c2} de nivel 2 y {c1} de nivel 1. El evento más "
              "relevante fue <b>{top}</b> en la fase de {phase}, con un pico de {peak} {u} frente a un umbral de nivel {lvl} "
              "de {th} {u}. Las acciones de mitigación recomendadas están en la sección 4 y deben ser validadas por el "
              "Safety Manager antes de su implantación."},
    "sum_none": {
        "pt": "Foram descodificados {np} parâmetros ao longo de {dur} de gravação e avaliados {nav} dos {nt} eventos do "
              "programa, sem excedências aos limiares definidos.",
        "en": "{np} parameters were decoded over {dur} of recording and {nav} of the {nt} programme events were evaluated, "
              "with no exceedances of the defined thresholds.",
        "fr": "{np} paramètres ont été décodés sur {dur} d'enregistrement et {nav} des {nt} événements du programme ont été "
              "évalués, sans dépassement des seuils définis.",
        "es": "Se decodificaron {np} parámetros a lo largo de {dur} de grabación y se evaluaron {nav} de los {nt} eventos "
              "del programa, sin superación de los umbrales definidos."},
    "cap_profile": {"pt": "Perfil vertical com fases detetadas automaticamente; marcadores indicam o nível de risco dos eventos.",
                    "en": "Vertical profile with automatically detected phases; markers show the risk level of each event.",
                    "fr": "Profil vertical avec phases détectées automatiquement ; les repères indiquent le niveau de risque.",
                    "es": "Perfil vertical con fases detectadas automáticamente; los marcadores indican el nivel de riesgo."},
    "route": {"pt": "Rota e localização dos eventos", "en": "Route and event locations",
              "fr": "Route et localisation des événements", "es": "Ruta y localización de los eventos"},
    "cap_route": {"pt": "Trajetória descodificada do QAR, colorida pela altitude-pressão. Os números correspondem aos eventos da secção 3.",
                  "en": "Flight path decoded from the QAR, coloured by pressure altitude. Numbers match the events in section 3.",
                  "fr": "Trajectoire décodée du QAR, colorée selon l'altitude-pression. Les numéros renvoient aux événements de la section 3.",
                  "es": "Trayectoria decodificada del QAR, coloreada por altitud de presión. Los números corresponden a los eventos de la sección 3."},
    "dep_map": {"pt": "Descolagem e subida inicial", "en": "Take-off and initial climb",
                "fr": "Décollage et montée initiale", "es": "Despegue y ascenso inicial"},
    "app_map": {"pt": "Aproximação final", "en": "Final approach", "fr": "Approche finale", "es": "Aproximación final"},
    "overview": {"pt": "Parâmetros principais ao longo do voo", "en": "Main parameters throughout the flight",
                 "fr": "Principaux paramètres au cours du vol", "es": "Parámetros principales a lo largo del vuelo"},
    "s2": {"pt": "2. Parâmetros monitorizados", "en": "2. Monitored parameters", "fr": "2. Paramètres surveillés",
           "es": "2. Parámetros monitorizados"},
    "s2_intro": {"pt": "Cada evento é avaliado contra três limiares. Nível 1 (baixo) é monitorizado em tendência, nível 2 (médio) "
                       "exige revisão pela equipa FDM e nível 3 (alto) exige ação imediata.",
                 "en": "Each event is assessed against three thresholds. Level 1 (low) is trend-monitored, level 2 (medium) "
                       "requires FDM team review and level 3 (high) requires immediate action.",
                 "fr": "Chaque événement est évalué selon trois seuils. Le niveau 1 (faible) est suivi en tendance, le niveau 2 "
                       "(moyen) exige une revue par l'équipe FDM et le niveau 3 (élevé) une action immédiate.",
                 "es": "Cada evento se evalúa frente a tres umbrales. El nivel 1 (bajo) se sigue en tendencia, el nivel 2 "
                       "(medio) requiere revisión del equipo FDM y el nivel 3 (alto) requiere acción inmediata."},
    "th_event": {"pt": "Evento / parâmetro", "en": "Event / parameter", "fr": "Événement / paramètre", "es": "Evento / parámetro"},
    "th_peak": {"pt": "Pico medido", "en": "Measured peak", "fr": "Pic mesuré", "es": "Pico medido"},
    "th_class": {"pt": "Classificação", "en": "Classification", "fr": "Classification", "es": "Clasificación"},
    "th_n": {"pt": "Nº", "en": "No.", "fr": "Nb", "es": "Nº"},
    "not_eval": {"pt": "não avaliado: falta {x}", "en": "not evaluated: missing {x}", "fr": "non évalué : manque {x}",
                 "es": "no evaluado: falta {x}"},
    "out_phase": {"pt": "fora de fase", "en": "outside phase", "fr": "hors phase", "es": "fuera de fase"},
    "s3": {"pt": "3. Eventos detetados", "en": "3. Detected events", "fr": "3. Événements détectés", "es": "3. Eventos detectados"},
    "no_events": {"pt": "Sem eventos neste voo.", "en": "No events on this flight.", "fr": "Aucun événement sur ce vol.",
                  "es": "Sin eventos en este vuelo."},
    "ev_sub": {"pt": "Código {c} · disparador {p} {op} {lims} {u} · fases: {ph}",
               "en": "Code {c} · trigger {p} {op} {lims} {u} · phases: {ph}",
               "fr": "Code {c} · déclencheur {p} {op} {lims} {u} · phases : {ph}",
               "es": "Código {c} · disparador {p} {op} {lims} {u} · fases: {ph}"},
    "all": {"pt": "todas", "en": "all", "fr": "toutes", "es": "todas"},
    "cond": {"pt": "condição", "en": "condition", "fr": "condition", "es": "condición"},
    "ev_text": {"pt": "De {a} a {b} desde o início do segmento ({ph}): pico {pk} {u}.",
                "en": "From {a} to {b} after segment start ({ph}): peak {pk} {u}.",
                "fr": "De {a} à {b} depuis le début du segment ({ph}) : pic {pk} {u}.",
                "es": "De {a} a {b} desde el inicio del segmento ({ph}): pico {pk} {u}."},
    "derived_note": {"pt": "Usa parâmetro(s) derivado(s) pela plataforma: {x}. Confirmar com o parâmetro gravado quando o LFL o disponibilizar.",
                     "en": "Uses parameter(s) derived by the platform: {x}. Confirm with the recorded parameter once the LFL provides it.",
                     "fr": "Utilise un ou des paramètres dérivés par la plateforme : {x}. À confirmer avec le paramètre enregistré dès que le LFL le fournit.",
                     "es": "Usa parámetro(s) derivado(s) por la plataforma: {x}. Confirmar con el parámetro grabado cuando el LFL lo facilite."},
    "s4": {"pt": "4. Plano de mitigação de risco", "en": "4. Risk mitigation plan", "fr": "4. Plan d'atténuation des risques",
           "es": "4. Plan de mitigación de riesgos"},
    "no_events_trend": {"pt": "Sem eventos neste voo. Manter monitorização em tendência.",
                        "en": "No events on this flight. Continue trend monitoring.",
                        "fr": "Aucun événement sur ce vol. Maintenir le suivi en tendance.",
                        "es": "Sin eventos en este vuelo. Mantener el seguimiento de tendencias."},
    "th_level": {"pt": "Nível", "en": "Level", "fr": "Niveau", "es": "Nivel"},
    "th_actions": {"pt": "Ações de mitigação recomendadas", "en": "Recommended mitigation actions",
                   "fr": "Actions d'atténuation recommandées", "es": "Acciones de mitigación recomendadas"},
    "th_owner": {"pt": "Responsável", "en": "Owner", "fr": "Responsable", "es": "Responsable"},
    "th_due": {"pt": "Prazo", "en": "Due", "fr": "Délai", "es": "Plazo"},
    "own1": {"pt": "Equipa FDM", "en": "FDM team", "fr": "Équipe FDM", "es": "Equipo FDM"},
    "own2": {"pt": "FDM + Gatekeeper", "en": "FDM + Gatekeeper", "fr": "FDM + Gatekeeper", "es": "FDM + Gatekeeper"},
    "own3": {"pt": "Safety Manager", "en": "Safety Manager", "fr": "Safety Manager", "es": "Safety Manager"},
    "due1": {"pt": "Revisão mensal", "en": "Monthly review", "fr": "Revue mensuelle", "es": "Revisión mensual"},
    "due2": {"pt": "≤ 7 dias", "en": "≤ 7 days", "fr": "≤ 7 jours", "es": "≤ 7 días"},
    "due3": {"pt": "Imediato (≤ 24 h)", "en": "Immediate (≤ 24 h)", "fr": "Immédiat (≤ 24 h)", "es": "Inmediato (≤ 24 h)"},
    "trend_only": {"pt": "Monitorizar em tendência.", "en": "Monitor in trend.", "fr": "Suivre en tendance.",
                   "es": "Seguir en tendencia."},
    "method": {"pt": "Notas metodológicas", "en": "Methodology notes", "fr": "Notes méthodologiques", "es": "Notas metodológicas"},
    "method_txt": {
        "pt": "Os dados foram descodificados a partir do ficheiro bruto ARINC 717 com base no Data Frame Layout do perfil "
              "indicado. As fases de voo são detetadas automaticamente. Os limiares e ações de mitigação devem corresponder ao "
              "programa FDM aprovado do operador e às limitações do fabricante (AFM/FCOM/AMM). Este relatório não substitui a "
              "análise humana de cada evento de nível 2 e 3.",
        "en": "Data were decoded from the raw ARINC 717 file using the Data Frame Layout of the stated profile. Flight phases "
              "are detected automatically. Thresholds and mitigation actions must match the operator's approved FDM programme "
              "and the manufacturer's limitations (AFM/FCOM/AMM). This report does not replace human review of every level 2 "
              "and level 3 event.",
        "fr": "Les données ont été décodées à partir du fichier brut ARINC 717 selon le Data Frame Layout du profil indiqué. "
              "Les phases de vol sont détectées automatiquement. Les seuils et actions d'atténuation doivent correspondre au "
              "programme FDM approuvé de l'exploitant et aux limitations du constructeur (AFM/FCOM/AMM). Ce rapport ne remplace "
              "pas l'analyse humaine de chaque événement de niveau 2 et 3.",
        "es": "Los datos se decodificaron del fichero bruto ARINC 717 según el Data Frame Layout del perfil indicado. Las fases "
              "de vuelo se detectan automáticamente. Los umbrales y acciones de mitigación deben corresponder al programa FDM "
              "aprobado del operador y a las limitaciones del fabricante (AFM/FCOM/AMM). Este informe no sustituye el análisis "
              "humano de cada evento de nivel 2 y 3."},
    "annex": {"pt": "Anexo A. Dados e mapeamento de parâmetros", "en": "Annex A. Data and parameter mapping",
              "fr": "Annexe A. Données et correspondance des paramètres", "es": "Anexo A. Datos y mapeo de parámetros"},
    "annex_txt": {"pt": "Ficheiro com {dur} de gravação, {wps} palavras por segundo, formato {fmt}, sincronismo válido em {q}% dos subframes ({sl} perdas).",
                  "en": "File with {dur} of recording, {wps} words per second, {fmt} format, valid sync in {q}% of subframes ({sl} losses).",
                  "fr": "Fichier de {dur} d'enregistrement, {wps} mots par seconde, format {fmt}, synchronisation valide sur {q} % des sous-trames ({sl} pertes).",
                  "es": "Fichero con {dur} de grabación, {wps} palabras por segundo, formato {fmt}, sincronismo válido en el {q} % de las subtramas ({sl} pérdidas)."},
    "th_param": {"pt": "Parâmetro", "en": "Parameter", "fr": "Paramètre", "es": "Parámetro"},
    "th_loc": {"pt": "Subframe / palavra", "en": "Subframe / word", "fr": "Sous-trame / mot", "es": "Subtrama / palabra"},
    "th_enc": {"pt": "Codificação", "en": "Encoding", "fr": "Codage", "es": "Codificación"},
    "th_scale": {"pt": "Escala", "en": "Scale", "fr": "Échelle", "es": "Escala"},
    "th_evid": {"pt": "Evidência / descrição", "en": "Evidence / description", "fr": "Preuve / description", "es": "Evidencia / descripción"},
    "derived_title": {"pt": "Parâmetros derivados pela plataforma", "en": "Parameters derived by the platform",
                      "fr": "Paramètres dérivés par la plateforme", "es": "Parámetros derivados por la plataforma"},
    "haa_note": {"pt": "Height Above Airfield = altitude-pressão menos a do aeródromo (partida/chegada).",
                 "en": "Height Above Airfield = pressure altitude minus that of the airfield (departure/arrival).",
                 "fr": "Height Above Airfield = altitude-pression moins celle de l'aérodrome (départ/arrivée).",
                 "es": "Height Above Airfield = altitud de presión menos la del aeródromo (salida/llegada)."},
    "all_sf": {"pt": "todos", "en": "all", "fr": "toutes", "es": "todas"},
    "fine": {"pt": "+ fina", "en": "+ fine", "fr": "+ fin", "es": "+ fina"},
    # gráficos
    "ax_alt": {"pt": "Altitude-pressão (ft)", "en": "Pressure altitude (ft)", "fr": "Altitude-pression (ft)", "es": "Altitud de presión (ft)"},
    "ax_tmin": {"pt": "Tempo desde o início do segmento (min)", "en": "Time from segment start (min)",
                "fr": "Temps depuis le début du segment (min)", "es": "Tiempo desde el inicio del segmento (min)"},
    "ax_ts": {"pt": "Tempo desde o início do segmento (s)", "en": "Time from segment start (s)",
              "fr": "Temps depuis le début du segment (s)", "es": "Tiempo desde el inicio del segmento (s)"},
    "ax_lat": {"pt": "Latitude (°)", "en": "Latitude (°)", "fr": "Latitude (°)", "es": "Latitud (°)"},
    "ax_lon": {"pt": "Longitude (°)", "en": "Longitude (°)", "fr": "Longitude (°)", "es": "Longitud (°)"},
    "ax_altft": {"pt": "Altitude (ft)", "en": "Altitude (ft)", "fr": "Altitude (ft)", "es": "Altitud (ft)"},

    # ---------------- Portal ----------------
    "lang": {"pt": "Idioma", "en": "Language", "fr": "Langue", "es": "Idioma"},
    "login_user": {"pt": "Email ou utilizador", "en": "Email or username", "fr": "E-mail ou identifiant", "es": "Email o usuario"},
    "login_pw": {"pt": "Palavra-passe", "en": "Password", "fr": "Mot de passe", "es": "Contraseña"},
    "login_btn": {"pt": "Entrar", "en": "Sign in", "fr": "Se connecter", "es": "Entrar"},
    "login_bad": {"pt": "Credenciais inválidas.", "en": "Invalid credentials.", "fr": "Identifiants invalides.", "es": "Credenciales no válidas."},
    "no_fdm": {"pt": "O módulo FDM não está incluído na sua licença. Contacte info@vektor.aero.",
               "en": "The FDM module is not part of your licence. Contact info@vektor.aero.",
               "fr": "Le module FDM ne fait pas partie de votre licence. Contactez info@vektor.aero.",
               "es": "El módulo FDM no está incluido en su licencia. Contacte con info@vektor.aero."},
    "signout": {"pt": "Sair", "en": "Sign out", "fr": "Se déconnecter", "es": "Salir"},
    "nav": {"pt": "Navegação", "en": "Navigation", "fr": "Navigation", "es": "Navegación"},
    "p_upload": {"pt": "Enviar dados de voo", "en": "Upload flight data", "fr": "Envoyer des données de vol", "es": "Enviar datos de vuelo"},
    "p_reports": {"pt": "Os meus relatórios", "en": "My reports", "fr": "Mes rapports", "es": "Mis informes"},
    "p_trends": {"pt": "Frota e tendências", "en": "Fleet and trends", "fr": "Flotte et tendances", "es": "Flota y tendencias"},
    "p_account": {"pt": "Conta e subscrição", "en": "Account and subscription", "fr": "Compte et abonnement", "es": "Cuenta y suscripción"},
    "p_review": {"pt": "Aprovações", "en": "Approvals", "fr": "Validations", "es": "Aprobaciones"},
    "p_subs": {"pt": "Todas as submissões", "en": "All submissions", "fr": "Toutes les soumissions", "es": "Todos los envíos"},
    "p_clients": {"pt": "Clientes e subscrições", "en": "Clients and subscriptions", "fr": "Clients et abonnements", "es": "Clientes y suscripciones"},
    "p_analyse": {"pt": "Análise livre", "en": "Ad-hoc analysis", "fr": "Analyse libre", "es": "Análisis libre"},
    "p_profiles": {"pt": "Perfis de aeronave", "en": "Aircraft profiles", "fr": "Profils avion", "es": "Perfiles de aeronave"},
    "aircraft": {"pt": "Aeronave", "en": "Aircraft", "fr": "Aéronef", "es": "Aeronave"},
    "no_aircraft": {"pt": "Ainda não há aeronaves associadas à sua conta. Contacte info@vektor.aero.",
                    "en": "No aircraft are linked to your account yet. Contact info@vektor.aero.",
                    "fr": "Aucun aéronef n'est encore associé à votre compte. Contactez info@vektor.aero.",
                    "es": "Todavía no hay aeronaves asociadas a su cuenta. Contacte con info@vektor.aero."},
    "file": {"pt": "Ficheiro do download (QAR/DFDR/MQAR: .dat, .tsc, .raw)", "en": "Download file (QAR/DFDR/MQAR: .dat, .tsc, .raw)",
             "fr": "Fichier de téléchargement (QAR/DFDR/MQAR : .dat, .tsc, .raw)", "es": "Fichero de descarga (QAR/DFDR/MQAR: .dat, .tsc, .raw)"},
    "notes": {"pt": "Notas para o analista (opcional)", "en": "Notes for the analyst (optional)",
              "fr": "Notes pour l'analyste (facultatif)", "es": "Notas para el analista (opcional)"},
    "send": {"pt": "Enviar e analisar", "en": "Send and analyse", "fr": "Envoyer et analyser", "es": "Enviar y analizar"},
    "processing": {"pt": "A descodificar e a analisar...", "en": "Decoding and analysing...", "fr": "Décodage et analyse...",
                   "es": "Decodificando y analizando..."},
    "sent_ok": {"pt": "Recebido. {n} voo(s) analisado(s). O relatório fica disponível após revisão pela Vektor.",
                "en": "Received. {n} flight(s) analysed. The report will be available after review by Vektor.",
                "fr": "Reçu. {n} vol(s) analysé(s). Le rapport sera disponible après revue par Vektor.",
                "es": "Recibido. {n} vuelo(s) analizado(s). El informe estará disponible tras la revisión de Vektor."},
    "sent_err": {"pt": "Recebido, mas a análise automática falhou. A Vektor foi notificada e vai tratar o ficheiro.",
                 "en": "Received, but the automatic analysis failed. Vektor has been notified and will process the file.",
                 "fr": "Reçu, mais l'analyse automatique a échoué. Vektor a été notifié et traitera le fichier.",
                 "es": "Recibido, pero el análisis automático falló. Vektor ha sido notificado y tratará el fichero."},
    "st_processing": {"pt": "Em análise", "en": "Processing", "fr": "En cours", "es": "En análisis"},
    "st_pending_review": {"pt": "Em revisão", "en": "Under review", "fr": "En revue", "es": "En revisión"},
    "st_approved": {"pt": "Aprovado", "en": "Approved", "fr": "Validé", "es": "Aprobado"},
    "st_rejected": {"pt": "Devolvido", "en": "Returned", "fr": "Retourné", "es": "Devuelto"},
    "st_error": {"pt": "Erro de análise", "en": "Analysis error", "fr": "Erreur d'analyse", "es": "Error de análisis"},
    "uploaded": {"pt": "Enviado", "en": "Uploaded", "fr": "Envoyé", "es": "Enviado"},
    "status": {"pt": "Estado", "en": "Status", "fr": "Statut", "es": "Estado"},
    "flights": {"pt": "Voos", "en": "Flights", "fr": "Vols", "es": "Vuelos"},
    "max_risk": {"pt": "Risco máximo", "en": "Highest risk", "fr": "Risque max.", "es": "Riesgo máximo"},
    "download_pdf": {"pt": "Descarregar relatório PDF", "en": "Download PDF report", "fr": "Télécharger le rapport PDF",
                     "es": "Descargar informe PDF"},
    "locked_pay": {"pt": "Relatório aprovado. Fica disponível para download quando a subscrição estiver ativa.",
                   "en": "Report approved. It becomes available for download once your subscription is active.",
                   "fr": "Rapport validé. Il sera téléchargeable dès que votre abonnement sera actif.",
                   "es": "Informe aprobado. Estará disponible para descarga cuando la suscripción esté activa."},
    "pay_now": {"pt": "Ativar subscrição", "en": "Activate subscription", "fr": "Activer l'abonnement", "es": "Activar suscripción"},
    "pay_manual": {"pt": "Pagamento por fatura: a Vektor ativa a subscrição após boa cobrança. Dúvidas: info@vektor.aero.",
                   "en": "Invoice payment: Vektor activates the subscription once payment is received. Questions: info@vektor.aero.",
                   "fr": "Paiement sur facture : Vektor active l'abonnement à réception du paiement. Questions : info@vektor.aero.",
                   "es": "Pago por factura: Vektor activa la suscripción al recibir el pago. Dudas: info@vektor.aero."},
    "sub_active": {"pt": "Subscrição ativa", "en": "Subscription active", "fr": "Abonnement actif", "es": "Suscripción activa"},
    "sub_inactive": {"pt": "Subscrição inativa", "en": "Subscription inactive", "fr": "Abonnement inactif", "es": "Suscripción inactiva"},
    "until": {"pt": "até {d}", "en": "until {d}", "fr": "jusqu'au {d}", "es": "hasta {d}"},
    "returned_note": {"pt": "Nota da Vektor", "en": "Note from Vektor", "fr": "Note de Vektor", "es": "Nota de Vektor"},
    "nothing_yet": {"pt": "Ainda não há envios.", "en": "No uploads yet.", "fr": "Aucun envoi pour l'instant.", "es": "Todavía no hay envíos."},
    "trend_locked": {"pt": "As tendências ficam disponíveis com a subscrição ativa.", "en": "Trends are available with an active subscription.",
                     "fr": "Les tendances sont disponibles avec un abonnement actif.", "es": "Las tendencias están disponibles con la suscripción activa."},
    "n_flights": {"pt": "Voos analisados", "en": "Flights analysed", "fr": "Vols analysés", "es": "Vuelos analizados"},
    "n_events": {"pt": "Eventos totais", "en": "Total events", "fr": "Événements", "es": "Eventos totales"},
    "l3_rate": {"pt": "Eventos nível 3 por 100 voos", "en": "Level 3 events per 100 flights", "fr": "Événements niveau 3 / 100 vols",
                "es": "Eventos nivel 3 por 100 vuelos"},
    "fleet": {"pt": "Aeronaves", "en": "Aircraft", "fr": "Aéronefs", "es": "Aeronaves"},
    "ev_by_type": {"pt": "Eventos por tipo e nível", "en": "Events by type and level", "fr": "Événements par type et niveau",
                   "es": "Eventos por tipo y nivel"},
    "risk_trend": {"pt": "Índice de risco médio por voo", "en": "Average risk index per flight", "fr": "Indice de risque moyen par vol",
                   "es": "Índice de riesgo medio por vuelo"},
    "view_flight": {"pt": "Ver gráficos e mapa", "en": "View charts and map", "fr": "Voir graphiques et carte",
                    "es": "Ver gráficos y mapa"},
    "report_lang": {"pt": "Idioma do relatório", "en": "Report language", "fr": "Langue du rapport", "es": "Idioma del informe"},
}

# Ações de mitigação padrão (importador de event sets e perfis de exemplo)
MITIGATION = {
    "Registar em tendência mensal por aeroporto, procedimento e tipo de operação.": {
        "en": "Record in the monthly trend by airport, procedure and type of operation.",
        "fr": "Enregistrer dans la tendance mensuelle par aéroport, procédure et type d'exploitation.",
        "es": "Registrar en la tendencia mensual por aeropuerto, procedimiento y tipo de operación."},
    "Incluir o tema na próxima comunicação de Safety Promotion se a tendência subir.": {
        "en": "Include the topic in the next Safety Promotion communication if the trend rises.",
        "fr": "Inclure le sujet dans la prochaine communication de promotion de la sécurité si la tendance augmente.",
        "es": "Incluir el tema en la próxima comunicación de Safety Promotion si la tendencia aumenta."},
    "Revisão pela equipa FDM com validação dos dados e contexto (meteorologia, ATC, NOTAM).": {
        "en": "FDM team review with validation of the data and context (weather, ATC, NOTAM).",
        "fr": "Revue par l'équipe FDM avec validation des données et du contexte (météo, ATC, NOTAM).",
        "es": "Revisión por el equipo FDM con validación de los datos y del contexto (meteorología, ATC, NOTAM)."},
    "Contacto confidencial à tripulação através do gatekeeper.": {
        "en": "Confidential crew contact through the gatekeeper.",
        "fr": "Contact confidentiel avec l'équipage via le gatekeeper.",
        "es": "Contacto confidencial con la tripulación a través del gatekeeper."},
    "Verificar conformidade com o SOP e propor reforço em briefing ou treino recorrente.": {
        "en": "Check SOP compliance and propose reinforcement in briefings or recurrent training.",
        "fr": "Vérifier la conformité aux SOP et proposer un renforcement en briefing ou en entraînement périodique.",
        "es": "Verificar el cumplimiento del SOP y proponer refuerzo en briefing o entrenamiento periódico."},
    "Comunicar ao Safety Manager em 24 h e abrir investigação no SMS.": {
        "en": "Report to the Safety Manager within 24 h and open an SMS investigation.",
        "fr": "Informer le Safety Manager sous 24 h et ouvrir une enquête SGS.",
        "es": "Comunicar al Safety Manager en 24 h y abrir una investigación en el SMS."},
    "Avaliar obrigação de reporte MOR ao abrigo do Reg. (UE) 376/2014 (72 h).": {
        "en": "Assess the MOR reporting obligation under Reg. (EU) 376/2014 (72 h).",
        "fr": "Évaluer l'obligation de notification MOR au titre du Règl. (UE) 376/2014 (72 h).",
        "es": "Evaluar la obligación de notificación MOR según el Reg. (UE) 376/2014 (72 h)."},
    "Avaliar inspeção de Manutenção quando aplicável (AMM) e treino adicional da tripulação.": {
        "en": "Assess a maintenance inspection where applicable (AMM) and additional crew training.",
        "fr": "Évaluer une inspection de maintenance le cas échéant (AMM) et un entraînement complémentaire de l'équipage.",
        "es": "Evaluar una inspección de mantenimiento cuando proceda (AMM) y entrenamiento adicional de la tripulación."},
}


def t(key: str, lang: str = DEFAULT, **kw) -> str:
    d = S.get(key)
    if d is None:
        return key
    txt = d.get(lang) or d.get("en") or d.get("pt") or key
    return txt.format(**kw) if kw else txt


def phase(code: str, lang: str = DEFAULT) -> str:
    return PHASES.get(lang, PHASES["pt"]).get(code, code)


def level(n: int, lang: str = DEFAULT) -> str:
    return LEVELS.get(lang, LEVELS["pt"]).get(int(n), str(n))


def mitigation(text: str, lang: str = DEFAULT) -> str:
    if lang == "pt":
        return text
    return MITIGATION.get(text, {}).get(lang, text)
