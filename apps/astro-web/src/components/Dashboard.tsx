import { AuthProvider } from "@/hooks/useAuth";
import { usePredictionWorkflow } from "@/hooks/usePredictionWorkflow";
import AuthGuard from "@/components/AuthGuard";
import ModelSelector from "@/components/ModelSelector";
import ImageDropzone from "@/components/ImageDropzone";
import PredictionResult from "@/components/PredictionResult";
import { useAuthContext } from "@/lib/auth";

export default function Dashboard() {
  return (
    <AuthProvider>
      <DashboardInner />
    </AuthProvider>
  );
}

function DashboardInner() {
  const { user, logout } = useAuthContext();
  const predictionWorkflow = usePredictionWorkflow();

  return (
    <AuthGuard>
      <div className="mx-auto flex min-h-dvh w-full max-w-[56rem] px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex w-full flex-col gap-6 pb-12">
          <header className="border-border bg-card motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 rounded-[4px] border px-5 py-4 motion-safe:duration-200 sm:flex sm:items-center sm:justify-between sm:px-6">
            <div className="min-w-0">
              <p className="text-foreground text-base leading-none font-bold">
                OncoRay
              </p>
              <p className="text-muted-foreground mt-1 text-xs leading-[1.3] font-normal tracking-[0.05em] uppercase">
                Default workflow: chest X-ray pneumonia classification
              </p>
            </div>
            <nav
              className="mt-4 flex flex-col gap-3 sm:mt-0 sm:flex-row sm:items-center sm:gap-4"
              aria-label="Workspace actions"
            >
              <span className="text-muted-foreground max-w-full truncate text-sm sm:max-w-xs">
                {user?.email}
              </span>
              <button
                type="button"
                onClick={logout}
                className="hover:text-foreground inline-flex min-h-11 items-center justify-center rounded-[4px] border border-[var(--color-opencode-border-outline)] px-5 py-1 text-sm font-medium text-[var(--color-opencode-mid-gray)] transition-[border-color,background-color,color] duration-150 hover:border-[var(--color-opencode-accent-blue)] active:bg-white/5"
              >
                Log out
              </button>
            </nav>
          </header>

          <section className="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-200">
            <ModelSelector
              value={predictionWorkflow.selectedMode}
              onValueChange={predictionWorkflow.selectMode}
            />
          </section>

          <section className="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-200">
            <ImageDropzone
              selectedMode={predictionWorkflow.selectedMode}
              uploadDraft={predictionWorkflow.uploadDraft}
              isRunning={predictionWorkflow.isRunning}
              canRun={predictionWorkflow.canRun}
              onSelectUpload={predictionWorkflow.selectUpload}
              onClearUpload={predictionWorkflow.clearUpload}
              onRunPrediction={predictionWorkflow.runPrediction}
            />
          </section>

          <PredictionResult prediction={predictionWorkflow.prediction} />
        </div>
      </div>
    </AuthGuard>
  );
}
