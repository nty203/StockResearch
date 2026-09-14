CREATE TABLE IF NOT EXISTS broker_reports (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker varchar(20) NOT NULL,
    name varchar(100) NOT NULL,
    firm varchar(100) NOT NULL,
    title text NOT NULL,
    date date NOT NULL,
    link text,
    created_at timestamptz DEFAULT now(),
    UNIQUE (ticker, firm, date, title)
);

CREATE INDEX IF NOT EXISTS idx_broker_reports_ticker_date ON broker_reports (ticker, date DESC);

-- RLS
ALTER TABLE broker_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read access for all users"
    ON broker_reports FOR SELECT
    USING (true);

CREATE POLICY "Enable insert/update for service role"
    ON broker_reports FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
