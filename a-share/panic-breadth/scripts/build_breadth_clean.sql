SET statement_timeout = 0;
DROP TABLE IF EXISTS breadth_clean;
CREATE UNLOGGED TABLE breadth_clean AS
WITH base AS (
  SELECT s.ts_code, s.trade_date,
         LEAST(GREATEST(s.pct_chg, -21), 21) AS pctw,
         s.pct_chg,
         s.close * COALESCE(a.adj_factor, 1) AS ac,
         s.low  * COALESCE(a.adj_factor, 1) AS al,
         s.total_mv
  FROM stock_daily s
  LEFT JOIN stock_adj_factor a
    ON a.ts_code = s.ts_code AND a.trade_date = s.trade_date
  WHERE s.trade_date >= DATE '2005-01-01'
    AND s.pct_chg IS NOT NULL
    AND right(s.ts_code, 2) <> 'BJ'
),
w AS (
  SELECT ts_code, trade_date, pctw, pct_chg, ac, al, total_mv,
         min(al) OVER w20 AS low20,
         count(*) OVER w20 AS cnt20,
         lag(total_mv) OVER wp AS prev_mv,
         lead(ac, 5) OVER wp AS ac5,
         lead(ac, 20) OVER wp AS ac20
  FROM base
  WINDOW w20 AS (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING),
         wp  AS (PARTITION BY ts_code ORDER BY trade_date)
)
SELECT trade_date,
  count(*) FILTER (WHERE cnt20 = 20) AS n,
  avg(pctw) FILTER (WHERE cnt20 = 20) AS ew_ret,
  (sum(pctw * prev_mv) FILTER (WHERE cnt20 = 20 AND prev_mv IS NOT NULL)
   / NULLIF(sum(prev_mv) FILTER (WHERE cnt20 = 20 AND prev_mv IS NOT NULL), 0)) AS vw_ret,
  count(*) FILTER (WHERE cnt20 = 20 AND pct_chg <= -5) AS c_dn5,
  count(*) FILTER (WHERE cnt20 = 20 AND pct_chg <= -7) AS c_dn7,
  count(*) FILTER (WHERE cnt20 = 20 AND pct_chg <= -9.5) AS c_dn95,
  count(*) FILTER (WHERE cnt20 = 20 AND pct_chg >= 5) AS c_up5,
  count(*) FILTER (WHERE cnt20 = 20 AND pct_chg >= 9.5) AS c_up95,
  count(*) FILTER (WHERE cnt20 = 20 AND ac <= low20) AS c_newlow,
  count(*) FILTER (WHERE cnt20 = 20 AND ac <= low20 AND pct_chg <= -5) AS c_low_dn5,
  avg(LEAST(GREATEST(ac5 / ac - 1, -0.85), 2.5)) FILTER (WHERE cnt20 = 20 AND ac5 IS NOT NULL) AS fw5_all,
  avg(LEAST(GREATEST(ac5 / ac - 1, -0.85), 2.5)) FILTER (WHERE cnt20 = 20 AND ac5 IS NOT NULL AND pct_chg <= -5) AS fw5_dn5,
  avg(LEAST(GREATEST(ac20 / ac - 1, -0.85), 2.5)) FILTER (WHERE cnt20 = 20 AND ac20 IS NOT NULL) AS fw20_all,
  avg(LEAST(GREATEST(ac20 / ac - 1, -0.85), 2.5)) FILTER (WHERE cnt20 = 20 AND ac20 IS NOT NULL AND pct_chg <= -5) AS fw20_dn5
FROM w
GROUP BY trade_date
ORDER BY trade_date;
