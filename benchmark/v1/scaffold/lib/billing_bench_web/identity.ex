defmodule BillingBenchWeb.Identity do
  @moduledoc "Verifies scaffold-issued identities; domain authorization belongs to the application."
  import Plug.Conn

  def init(options), do: options

  def call(conn, _options) do
    conn = fetch_cookies(conn)
    token =
      case get_req_header(conn, "authorization") do
        ["Bearer " <> value] -> value
        [] -> conn.cookies["billing_token"]
        _ -> nil
      end

    assign(conn, :current_actor, verify(token))
  end

  def verify(token) when is_binary(token) do
    with [payload, signature] <- String.split(token, "."),
         {:ok, given} <- Base.url_decode64(signature, padding: false),
         expected = :crypto.mac(:hmac, :sha256, Application.fetch_env!(:billing_bench, :auth_secret), payload),
         true <- byte_size(given) == byte_size(expected),
         true <- Plug.Crypto.secure_compare(given, expected),
         {:ok, json} <- Base.url_decode64(payload, padding: false),
         {:ok, %{"tenant_id" => tenant, "role" => role, "customer_id" => customer} = actor} <- Jason.decode(json),
         true <- is_nil(tenant) or is_binary(tenant),
         true <- role in ~w(platform_admin admin commercial billing revenue customer),
         true <- is_nil(customer) or is_binary(customer) do
      actor
    else
      _ -> nil
    end
  end

  def verify(_), do: nil
end
