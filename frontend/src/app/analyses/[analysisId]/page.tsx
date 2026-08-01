import { AnalysisWorkspace } from "@/components/analysis/analysis-workspace";

export default async function AnalysisPage({
  params,
}: {
  params: Promise<{ analysisId: string }>;
}) {
  const { analysisId } = await params;
  return <AnalysisWorkspace analysisId={analysisId} />;
}
