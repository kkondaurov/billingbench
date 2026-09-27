defmodule BillingBench.InfrastructureTest do
  use ExUnit.Case, async: false
  import Plug.Test

  setup do
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(BillingBench.Repo)
  end

  test "health reaches PostgreSQL" do
    conn = BillingBenchWeb.Endpoint.call(conn(:get, "/health"), [])
    assert conn.status == 200
    assert Jason.decode!(conn.resp_body) == %{"status" => "ok"}
  end

  test "Oban is supervised and its migration is present" do
    assert Oban.config().repo == BillingBench.Repo
    assert Oban.config().testing == :manual

    assert %{rows: [[true]]} =
             Ecto.Adapters.SQL.query!(
               BillingBench.Repo,
               "SELECT to_regclass('public.oban_jobs') IS NOT NULL",
               []
             )
  end
end
