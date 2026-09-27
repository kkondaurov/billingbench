defmodule BillingBenchWeb.Router do
  use Phoenix.Router

  get "/health", BillingBenchWeb.HealthController, :show
  get "/_session", BillingBenchWeb.SessionController, :show
  post "/_session", BillingBenchWeb.SessionController, :create
  delete "/_session", BillingBenchWeb.SessionController, :delete
end
