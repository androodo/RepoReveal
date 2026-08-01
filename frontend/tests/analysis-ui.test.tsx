import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnalysisProgress } from "@/components/analysis/analysis-progress";
import { AskTab } from "@/components/analysis/ask-tab";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  getStarterQuestions: vi.fn(async () => ({
    questions: ["Where does the application start?"],
  })),
  askRepository: vi.fn(),
  ApiError: class extends Error {},
}));

describe("AnalysisProgress", () => {
  it("renders stages and safety note", () => {
    render(<AnalysisProgress stage="parsing_python" progress={45} />);
    expect(screen.getAllByText(/Parsing Python/).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/RepoReveal analyzes source text only. It never executes repository code./),
    ).toBeInTheDocument();
  });

  it("renders failed state with retry", async () => {
    const onRetry = vi.fn();
    render(
      <AnalysisProgress stage="failed" progress={20} errorMessage="Too large" onRetry={onRetry} />,
    );
    expect(screen.getByText("Analysis failed")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Retry analysis/i }));
    expect(onRetry).toHaveBeenCalled();
  });
});

describe("AskTab AI unavailable", () => {
  it("shows unavailable messaging", () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <AskTab analysisId="abc" aiAvailable={false} />
      </QueryClientProvider>,
    );
    expect(screen.getByText(/AI features are unavailable/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Ask a question about this repository/i)).toBeDisabled();
  });
});
