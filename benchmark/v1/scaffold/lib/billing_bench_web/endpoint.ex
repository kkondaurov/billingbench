defmodule BillingBenchWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :billing_bench

  plug Plug.Static, at: "/", from: :billing_bench, gzip: false, only: ~w(assets)
  plug Plug.RequestId
  plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]
  plug Plug.Parsers, parsers: [:urlencoded, :multipart, :json], pass: ["*/*"], json_decoder: Jason
  plug Plug.MethodOverride
  plug Plug.Head
  plug BillingBenchWeb.Identity
  plug BillingBenchWeb.Router
end
