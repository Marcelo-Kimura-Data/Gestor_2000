# Output real de `EXPLAIN (ANALYZE, BUFFERS)`

Capturado em Postgres 16, cache frio parcial, `work_mem = 4MB`.

## Q1 — relatório diário de vendas

```
QUERY PLAN                                                               
----------------------------------------------------------------------------------------------------------------------------------------
 Finalize Aggregate  (cost=32140.06..32140.07 rows=1 width=40) (actual time=317.226..319.279 rows=1 loops=1)
   Buffers: shared hit=6829 read=11790
   ->  Gather  (cost=32139.84..32140.05 rows=2 width=40) (actual time=314.272..319.255 rows=3 loops=1)
         Workers Planned: 2
         Workers Launched: 2
         Buffers: shared hit=6829 read=11790
         ->  Partial Aggregate  (cost=31139.84..31139.85 rows=1 width=40) (actual time=307.779..307.780 rows=1 loops=3)
               Buffers: shared hit=6829 read=11790
               ->  Parallel Seq Scan on pedidos  (cost=0.00..31119.00 rows=4167 width=6) (actual time=4.394..307.427 rows=1157 loops=3)
                     Filter: (date(created_at) = '2026-05-10'::date)
                     Rows Removed by Filter: 665510
                     Buffers: shared hit=6829 read=11790
 Planning:
   Buffers: shared hit=116 read=3
 Planning Time: 0.362 ms
 Execution Time: 319.346 ms
(16 rows)
```

## Q2 — fila de pedidos pendentes do app

```
QUERY PLAN                                                                     
---------------------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=0.43..542.76 rows=200 width=30) (actual time=0.046..21.282 rows=200 loops=1)
   Buffers: shared hit=3200 read=3854 written=138
   ->  Index Scan using idx_pedidos_created_at on pedidos  (cost=0.43..136422.98 rows=50310 width=30) (actual time=0.045..21.249 rows=200 loops=1)
         Filter: ((status = 'pendente'::text) AND (canal = 'app'::text))
         Rows Removed by Filter: 6832
         Buffers: shared hit=3200 read=3854 written=138
 Planning:
   Buffers: shared hit=49
 Planning Time: 0.261 ms
 Execution Time: 21.316 ms
(10 rows)
```

## Q3 — ranking de clientes por receita

```
QUERY PLAN                                                                        
---------------------------------------------------------------------------------------------------------------------------------------------------------
 Sort  (cost=182789.54..183233.03 rows=177397 width=48) (actual time=2985.527..3039.274 rows=199988 loops=1)
   Sort Key: (sum(total)) DESC
   Sort Method: external merge  Disk: 6656kB
   Buffers: shared hit=9257 read=9381, temp read=16375 written=24219
   ->  Finalize GroupAggregate  (cost=114702.59..161863.51 rows=177397 width=48) (actual time=2414.815..2880.152 rows=199988 loops=1)
         Group Key: cliente_id
         Buffers: shared hit=9254 read=9381, temp read=15543 written=23384
         ->  Gather Merge  (cost=114702.59..156098.11 rows=354794 width=48) (actual time=2414.745..2618.242 rows=578274 loops=1)
               Workers Planned: 2
               Workers Launched: 2
               Buffers: shared hit=9254 read=9381, temp read=15543 written=23384
               ->  Sort  (cost=113702.56..114146.06 rows=177397 width=48) (actual time=2361.767..2389.527 rows=192758 loops=3)
                     Sort Key: cliente_id
                     Sort Method: external merge  Disk: 17352kB
                     Buffers: shared hit=9254 read=9381, temp read=15543 written=23384
                     Worker 0:  Sort Method: external merge  Disk: 17136kB
                     Worker 1:  Sort Method: external merge  Disk: 17112kB
                     ->  Partial HashAggregate  (cost=82421.06..92776.54 rows=177397 width=48) (actual time=937.045..2114.967 rows=192758 loops=3)
                           Group Key: cliente_id
                           Planned Partitions: 8  Batches: 41  Memory Usage: 8273kB  Disk Usage: 23704kB
                           Buffers: shared hit=9238 read=9381, temp read=9093 written=16916
                           Worker 0:  Batches: 41  Memory Usage: 8273kB  Disk Usage: 23488kB
                           Worker 1:  Batches: 41  Memory Usage: 8273kB  Disk Usage: 23440kB
                           ->  Parallel Seq Scan on pedidos  (cost=0.00..26952.33 rows=833333 width=14) (actual time=0.025..157.298 rows=666667 loops=3)
                                 Buffers: shared hit=9238 read=9381
 Planning:
   Buffers: shared hit=14 read=1
 Planning Time: 0.133 ms
 JIT:
   Functions: 33
   Options: Inlining false, Optimization false, Expressions true, Deforming true
   Timing: Generation 2.986 ms, Inlining 0.000 ms, Optimization 8.657 ms, Emission 109.047 ms, Total 120.689 ms
 Execution Time: 3071.978 ms
(33 rows)
```

## Q4 — busca de produto no admin

```
QUERY PLAN                                                 
------------------------------------------------------------------------------------------------------------
 Seq Scan on produtos  (cost=0.00..449.00 rows=1919 width=47) (actual time=0.017..10.636 rows=1000 loops=1)
   Filter: (ativo AND (nome ~~* '%caneta%'::text))
   Rows Removed by Filter: 19000
   Buffers: shared hit=199
 Planning:
   Buffers: shared hit=47 read=6
 Planning Time: 0.370 ms
 Execution Time: 10.684 ms
(8 rows)
```
