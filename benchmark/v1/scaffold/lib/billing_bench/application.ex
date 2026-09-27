defmodule BillingBench.Application do
  use Application

  @impl true
  def start(_type, _args) do
    children = [
      BillingBench.Repo,
      {Phoenix.PubSub, name: BillingBench.PubSub},
      {Oban, Application.fetch_env!(:billing_bench, Oban)},
      BillingBenchWeb.Endpoint
    ]

    Supervisor.start_link(children, strategy: :one_for_one, name: BillingBench.Supervisor)
  end

  @impl true
  def config_change(changed, _new, removed) do
    BillingBenchWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
