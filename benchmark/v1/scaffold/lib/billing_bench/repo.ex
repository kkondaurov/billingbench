defmodule BillingBench.Repo do
  use Ecto.Repo, otp_app: :billing_bench, adapter: Ecto.Adapters.Postgres
end
