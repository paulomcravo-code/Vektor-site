# Vektor FDM · pôr a plataforma online (Render, Frankfurt)

Resultado: `https://fdm.vektor.aero` com o portal dos clientes, a tua consola de dono e o connector
para o Claude, num único serviço na UE. Tudo corre sozinho; o Claude é opcional (connector).

Custo indicativo: servidor 1 CPU / 2 GB (25 USD/mês) + disco de 20 GB (5 USD/mês) ≈ 30 USD/mês,
mais o plano de workspace do Render (Hobby 0 USD; Pro 25 USD se quiseres equipa e mais tráfego).

## Áreas depois do login
- `https://fdm.vektor.aero/admin`: área do dono (aprovações, submissões, clientes, tendências, análise livre, perfis).
- `https://fdm.vektor.aero/client`: área do cliente (relatórios, envio de dados, tendências, conta).
Cada perfil só tem acesso à sua área.

## 1. Código no GitHub (10 min)
1. Cria uma conta em github.com (se ainda não tiveres) e um repositório **privado** `vektor-fdm`.
2. Carrega o conteúdo desta pasta (Add file > Upload files, ou GitHub Desktop). Não carregues a pasta `data/`.

## 2. Serviço no Render (15 min)
1. Cria conta em render.com e liga o GitHub.
2. New > **Blueprint** > escolhe `vektor-fdm`. O ficheiro `render.yaml` cria o serviço `vektor-fdm` em
   Frankfurt com disco persistente em `/data` (base de dados, ficheiros originais, análises e PDFs).
3. Preenche as variáveis pedidas:
   - `OWNER_PASSWORD`: a tua palavra-passe de dono (longa, só tua). Entras com `fdm@vektor.aero` ou `owner`.
   - `SMTP_USER` / `SMTP_PASS`: caixa `fdm@vektor.aero` criada na Infomaniak (envio dos avisos por email).
   - `STRIPE_SECRET_KEY` e `STRIPE_PAYMENT_LINK`: ver passo 4 (podes deixar vazio e preencher depois).
   - `SECRET_KEY` e `MCP_TOKEN` são gerados automaticamente.
4. Deploy. Quando ficar "Live", abre o endereço `https://vektor-fdm.onrender.com` e entra como dono.

## 3. Domínio fdm.vektor.aero (10 min + propagação)
1. Render > serviço > Settings > Custom Domains > `fdm.vektor.aero`.
2. Infomaniak > Domínios > vektor.aero > Zona DNS > novo registo **CNAME** `fdm` → `vektor-fdm.onrender.com`.
3. O certificado HTTPS é emitido automaticamente. Atualiza `PORTAL_URL` se usares outro endereço.

## 4. Pagamentos
- **Fatura (manual):** na consola, Clientes e subscrições > marca "Subscrição paga" e a data limite.
  Os relatórios aprovados ficam logo disponíveis e o cliente recebe email.
- **Stripe (automático):** no Stripe cria o produto "Vektor FDM" com preço mensal ou anual e um
  *Payment Link*; cola-o em `STRIPE_PAYMENT_LINK` (ou um link por cliente na consola). Cria uma
  *restricted key* só de leitura (Customers: read, Subscriptions: read) e cola em `STRIPE_SECRET_KEY`.
  O cliente paga com o mesmo email do login; o portal confirma a subscrição ativa e liberta os relatórios.
- No cliente escolhe "Pagamento": Fatura, Stripe ou Ambos.

## 5. Connector no Claude
1. Render > Environment > copia o valor de `MCP_TOKEN`.
2. Claude > Definições > Connectors > Adicionar connector personalizado:
   nome `Vektor FDM`, URL `https://fdm.vektor.aero/mcp/<MCP_TOKEN>`.
3. O endereço com o token dá acesso de dono: não o partilhes. Para o revogar, muda `MCP_TOKEN` no Render.
Ferramentas: resumo da plataforma, clientes, submissões, eventos por voo, links de PDF, tendências,
aprovar/devolver, reprocessar, subscrições, criar cliente e associar aeronave.

## 6. Primeiro cliente
1. Consola > Clientes e subscrições > Novo cliente (ID, nome, email, idioma, módulos com FDM, pagamento).
   Em palavra-passe escreve `gerar`: aparece uma vez para enviares por canal seguro.
2. Associa as aeronaves (matrícula + perfil de descodificação).
3. O cliente entra em `https://fdm.vektor.aero`, envia o download, a análise corre de imediato e
   recebes email. Revês em Aprovações, aprovas, e o cliente descarrega o PDF (PT/EN/FR/ES) se a subscrição estiver ativa.

## Dados, cópias e RGPD
- Tudo fica no disco do serviço em Frankfurt (`/data`): só tu tens acesso total; cada cliente vê só o seu.
- O Render faz snapshots diários do disco (retidos 7 dias). Recomenda-se descarregar uma cópia mensal de `/data`
  (Render Shell) e assinar o DPA do Render.
- Registo de auditoria (logins, envios, aprovações, downloads) na tabela `audit`.
