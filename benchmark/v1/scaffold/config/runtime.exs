import Config

database_url = System.fetch_env!("DATABASE_URL")

# Tests use a separate database even when run inside the candidate container.
database_url =
  if config_env() == :test do
    System.get_env("TEST_DATABASE_URL") ||
      database_url |> URI.parse() |> Map.update!(:path, &(&1 <> "_test")) |> URI.to_string()
  else
    database_url
  end

config :billing_bench, BillingBench.Repo,
  url: database_url,
  pool_size: String.to_integer(System.get_env("POOL_SIZE", "10"))

config :billing_bench,
  gl_url: System.get_env("BILLING_GL_URL"),
  auth_secret: System.get_env("BILLING_AUTH_SECRET", "billingbench-local-development-only")

if oban_node = System.get_env("OBAN_NODE") do
  config :billing_bench, Oban, node: oban_node
end

if System.get_env("JOBS_ENABLED", "1") == "0" do
  config :billing_bench, Oban, queues: false
end

config :billing_bench, BillingBenchWeb.Endpoint,
  http: [ip: {0, 0, 0, 0}, port: String.to_integer(System.get_env("PORT", "4000"))],
  secret_key_base: System.fetch_env!("SECRET_KEY_BASE")

if server = System.get_env("PHX_SERVER") do
  config :billing_bench, BillingBenchWeb.Endpoint, server: server in ["1", "true"]
end
