
-- Q1: relatório diário de vendas (roda a cada 5 min no dashboard)

SELECT count(*) AS qtd, sum(total) AS receita
FROM pedidos
WHERE date(created_at) = '2026-05-10';

-- Q2: fila de pedidos pendentes do app (tela do time de operações)

SELECT id, cliente_id, total, created_at
FROM pedidos
WHERE status = 'pendente'
  AND canal = 'app'
ORDER BY created_at
LIMIT 200;

-- Q3: ranking de clientes por receita (relatório mensal do comercial)

SELECT cliente_id, count(*) AS pedidos, sum(total) AS receita
FROM pedidos
GROUP BY cliente_id
ORDER BY receita DESC;

-- Q4: busca de produto no admin

SELECT id, nome, categoria, preco
FROM produtos
WHERE nome ILIKE '%caneta%'
  AND ativo;
