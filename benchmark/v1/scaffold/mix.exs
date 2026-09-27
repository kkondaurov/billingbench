defmodule BillingBench.MixProject do
  use Mix.Project

  def project do
    [
      app: :billing_bench,
      version: "0.1.0",
      elixir: "~> 1.20",
      deps_path: System.get_env("MIX_DEPS_PATH") || "deps",
      start_permanent: Mix.env() == :prod,
      deps: deps(),
      aliases: [
        setup: ["deps.get", "ecto.create", "ecto.migrate"],
        test: ["ecto.create --quiet", "ecto.migrate --quiet", "test"]
      ]
    ]
  end

  def application do
    [mod: {BillingBench.Application, []}, extra_applications: [:logger, :inets, :ssl]]
  end

  defp deps do
    [
      {:phoenix, "== 1.8.12"},
      {:phoenix_ecto, "== 4.7.0"},
      {:ecto_sql, "== 3.14.0"},
      {:postgrex, "== 0.22.4"},
      {:oban, "== 2.24.1"},
      {:jason, "== 1.4.5"},
      {:decimal, "== 3.1.1"},
      {:bandit, "== 1.12.5"}
    ]
  end
end
