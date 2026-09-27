import Config

config :billing_bench, BillingBench.Repo, pool: Ecto.Adapters.SQL.Sandbox
config :billing_bench, Oban, testing: :manual
config :billing_bench, BillingBenchWeb.Endpoint, server: false
config :logger, level: :warning
