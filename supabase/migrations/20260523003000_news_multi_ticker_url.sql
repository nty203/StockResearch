-- Allow one article URL to be associated with multiple tickers.

ALTER TABLE news
  DROP CONSTRAINT IF EXISTS news_url_key;

CREATE UNIQUE INDEX IF NOT EXISTS news_ticker_url_key
  ON news(ticker, url);
