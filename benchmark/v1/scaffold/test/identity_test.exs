defmodule BillingBench.IdentityTest do
  use ExUnit.Case, async: true
  import Plug.Test
  import Plug.Conn

  defp token(actor) do
    payload = actor |> Jason.encode!() |> Base.url_encode64(padding: false)
    secret = Application.fetch_env!(:billing_bench, :auth_secret)
    signature = :crypto.mac(:hmac, :sha256, secret, payload) |> Base.url_encode64(padding: false)
    payload <> "." <> signature
  end

  test "bearer identity is verified without assigning domain permissions" do
    actor = %{"tenant_id" => "tenant-a", "role" => "billing", "customer_id" => nil}
    conn = conn(:get, "/") |> put_req_header("authorization", "Bearer " <> token(actor))
    assert BillingBenchWeb.Identity.call(conn, []).assigns.current_actor == actor
    assert BillingBenchWeb.Identity.verify(token(actor) <> "x") == nil
    assert BillingBenchWeb.Identity.verify(nil) == nil
  end

  test "session accepts the same signed identity and rejects tampering" do
    actor = %{"tenant_id" => "tenant-a", "role" => "customer", "customer_id" => "buyer"}
    conn = conn(:post, "/_session", %{"token" => token(actor)})
    response = BillingBenchWeb.Endpoint.call(conn, [])
    assert response.status == 302
    assert response.resp_cookies["billing_token"].http_only
    bad = BillingBenchWeb.Endpoint.call(conn(:post, "/_session", %{"token" => "invalid"}), [])
    assert bad.status == 401
  end
end
