import Config

config :billing_bench, ecto_repos: [BillingBench.Repo]
config :billing_bench, BillingBench.Repo, migration_timestamps: [type: :utc_datetime_usec]

config :billing_bench, BillingBenchWeb.Endpoint,
  adapter: Bandit.PhoenixAdapter,
  render_errors: [formats: [json: BillingBenchWeb.ErrorJSON], layout: false],
  pubsub_server: BillingBench.PubSub

config :billing_bench, Oban,
  repo: BillingBench.Repo,
  engine: Oban.Engines.Basic,
  lifeline: [rescue_after: {60, :seconds}, interval: {5, :seconds}],
  queues: [default: 10]

config :phoenix, :json_library, Jason
config :logger, :console, format: "$time $metadata[$level] $message\n"

import_config "#{config_env()}.exs"
