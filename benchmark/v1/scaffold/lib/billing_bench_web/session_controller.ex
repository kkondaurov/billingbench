defmodule BillingBenchWeb.SessionController do
  use Phoenix.Controller, formats: [:html, :json]

  def show(conn, _params) do
    html(conn, """
    <!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
    <title>Billing Bench sign in</title><body>
    <main><h1>Billing Bench</h1><form method="post" action="/_session">
    <label>Session token <input name="token" required autocomplete="off"></label>
    <button type="submit">Sign in</button></form></main></body></html>
    """)
  end

  def create(conn, %{"token" => token}) do
    case BillingBenchWeb.Identity.verify(token) do
      nil -> conn |> put_status(401) |> json(%{error: %{code: "unauthenticated", issues: []}})
      _ -> conn |> put_resp_cookie("billing_token", token, http_only: true, same_site: "Lax") |> redirect(to: "/")
    end
  end

  def create(conn, _), do: conn |> put_status(400) |> json(%{error: %{code: "invalid_request", issues: []}})
  def delete(conn, _), do: conn |> delete_resp_cookie("billing_token") |> redirect(to: "/_session")
end
