defmodule BillingBenchWeb.HealthController do
  use Phoenix.Controller, formats: [:json]

  def show(conn, _params) do
    Ecto.Adapters.SQL.query!(BillingBench.Repo, "SELECT 1", [])
    json(conn, %{status: "ok"})
  end
end
