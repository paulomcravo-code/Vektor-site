# Vektor FDM (MVP) · vektor.aero

Plataforma web para descodificar ficheiros brutos de QAR/DFDR (.dat, ARINC 717), detetar excedências com três níveis de risco (1 baixo, 2 médio, 3 alto), gerar gráficos por parâmetro, propor ações de mitigação e emitir um relatório PDF por voo, com histórico e tendências de frota por cliente.

## Executar localmente

```bash
pip install -r requirements.txt
python tools/gerar_dat_teste.py profiles/atr72_exemplo amostras/voo_teste.dat   # ficheiro de teste
streamlit run app.py
```

Linha de comando (lotes, um PDF por voo): `python cli.py download.tsc glex_p4bfw pasta_saida P4-BFW`

## Estrutura

| Pasta / ficheiro | Função |
|---|---|
| `fdm/decoder.py` | Leitura ARINC 717: deteção de sync words, ressincronização após dados corrompidos, extração de bits, conversão para unidades de engenharia |
| `fdm/phases.py` | Fases de voo automáticas (solo, descolagem, subida, cruzeiro, descida, aproximação, aterragem) |
| `fdm/events.py` | Motor de eventos: limiares N1/N2/N3, duração mínima, condições (ex.: RALT < 1000 ft), mitigação por nível |
| `fdm/report.py`, `fdm/charts.py` | Relatório PDF com síntese, tabela de parâmetros, gráfico por parâmetro e plano de mitigação |
| `fdm/storage.py` | Histórico de voos e eventos por cliente (SQLite; migrar para PostgreSQL em produção) |
| `profiles/<tipo>/frame_layout.yaml` | LFL / Data Frame Layout do fabricante (onde está cada parâmetro no ficheiro) |
| `profiles/<tipo>/events.yaml` | Catálogo de eventos, limiares e ações de mitigação |

## Downloads com vários voos, mapas e conjuntos de eventos

- Formatos de armazenamento: `word16`, `packed12` (bit mais significativo primeiro) e `packed12_lsb` (fluxo contínuo LSB primeiro, como nos ficheiros .tsc do MQAR). O deslocamento do primeiro sincronismo é encontrado automaticamente.
- Um download é separado em voos (`analyse_download`); cada voo tem o seu relatório, com perfil vertical, mapa da rota, pormenor de descolagem e aproximação e eventos numerados no mapa.
- Parâmetros em duas palavras (latitude/longitude) usam `fine_offset`; valores fora de alcance usam `invalid_above`; parâmetros derivados (`abs(...)`, `rate(...)`, expressões) vão em `derived:` no frame_layout.
- `tools/importar_event_set.py` converte um "Event Set Details" exportado do software do fornecedor para `events.yaml`: limiares e durações por nível (Low=1, Med=2, High=3), fases (células marcadas), condições com AND/OR, parâmetros desfasados no tempo (`[Vertical Speed(-90)]`) e disparadores calculados. A pasta `event_sets/` tem os conjuntos GLEX, G450, G550 e ERJ190 já convertidos.
- Dados geográficos offline em `assets/geo`: aeroportos OurAirports e linha de costa Natural Earth 1:50m (domínio público).

## Adicionar uma aeronave nova

1. Criar `profiles/<tipo>/` copiando o perfil de exemplo.
2. Preencher `frame_layout.yaml` a partir do documento de Data Frame Layout do fabricante ou do fornecedor do FDAU/FDIMU: palavras por segundo, formato de armazenamento, e para cada parâmetro subframe, palavra, bits, codificação, escala e offset.
3. Preencher `events.yaml` com os limiares do programa FDM aprovado e das limitações AFM/FCOM/AMM.
4. Validar com um voo conhecido (comparar valores descodificados com o software do fabricante) antes de uso operacional.

O perfil `atr72_exemplo` é fictício e serve apenas para testes.

## Publicar na internet (Docker)

```bash
docker build -t vektor-fdm .
docker run -p 8501:8501 -e APP_PASSWORD=... -v fdm_data:/data vektor-fdm
```

Variáveis:
- `APP_PASSWORD`: palavra-passe do dono (utilizador `owner`), que vê todos os clientes e os perfis de aeronave.
- `FDM_CLIENTS`: contas de cliente em JSON, `{"acme": {"name": "Acme Jets", "password_sha256": "<hash>", "modules": ["FDM", "SMS"]}}`. Cada cliente só vê e envia os seus voos, e só entra se a licença incluir o módulo FDM (os módulos são os mesmos da consola Vektor).
- `FDM_UPLOADS`: pasta onde ficam os .dat originais (por cliente e matrícula); em produção, armazenamento cifrado na UE.
- `FDM_BRAND`, `FDM_DB`: nome no relatório e caminho da base de dados.

## Portal de clientes e ligação ao Excel Vektor

Os clientes entram com a sua conta, enviam o download do QAR por aeronave e recebem o relatório PDF. O original fica guardado para reprocessamento. O botão "Exportar eventos para Excel Vektor" gera um CSV com as colunas da folha FDM_Events: no Excel, colar a partir da coluna A e os SPI do SMS (F01–F05) atualizam-se sozinhos.

## Próximos passos para versão comercial

- Autenticação real com contas por cliente e perfis (Safety Manager, analista FDM, gatekeeper) e MFA.
- PostgreSQL gerido e armazenamento de ficheiros em objeto (S3) cifrado, com retenção configurável.
- Processamento assíncrono (fila de trabalhos) para ficheiros de vários voos e segmentação automática de voos num mesmo download.
- Suporte a parâmetros multi-palavra, superframes e formatos ARINC 767 / ficheiros comprimidos de fornecedores.
- Desidentificação de tripulações e registo de auditoria de acessos.

## Marca e domínio

Plataforma da Vektor Aviation Consulting. Logótipo em `assets/vektor_mark.png` (usado no portal e no cabeçalho dos relatórios PDF). Endereço sugerido: `fdm.vektor.aero` (registo CNAME no DNS do domínio vektor.aero a apontar para o serviço alojado na UE). Depois de alojada, gravar o endereço na consola Vektor, separador Plataforma.

## Portal comercial online
Fluxo: cliente envia → análise automática → aprovação do dono → download quando a subscrição está ativa
(manual por fatura e/ou Stripe). Portal e relatórios em PT/EN/FR/ES. Servidor MCP (`mcp_server.py`) para ligar
a plataforma ao Claude como connector. Instalação: ver `DEPLOY.md`.

## Ficheiros L3 FA2100 (.fdr) e dados em CSV
- O `.fdr` descarregado do FA2100 vem comprimido em formato proprietário L3 (blocos de 64 KB com cabeçalhos 0xBEEF).
  A plataforma deteta-o e pede a versão expandida.
- Perfis com `storage: csv` leem diretamente uma exportação em unidades de engenharia (uma coluna por parâmetro,
  nomes alternativos em `columns`), com separação automática de voos. Exemplo: `profiles/b737_bbj`.
- `tools/importar_event_summary_pdf.py` converte um "Event Set Summary" (PDF Scaled Analytics). Operador, fases e faixas
  de altura são inferidos do nome; eventos que dependem de mudanças de estado ficam por avaliar até haver a exportação
  "Event Set Details".
