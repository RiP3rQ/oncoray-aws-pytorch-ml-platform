import { useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { AuthProvider } from "@/hooks/useAuth";
import { useAuthContext } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";

const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginForm() {
  return (
    <AuthProvider>
      <LoginFormInner />
    </AuthProvider>
  );
}

function LoginFormInner() {
  const { login } = useAuthContext();
  const [submitting, setSubmitting] = useState(false);
  const persistentRef = useRef<HTMLInputElement>(null);
  const emailId = useId();
  const passwordId = useId();
  const persistentId = useId();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: standardSchemaResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormValues) => {
    const persistent = persistentRef.current?.checked ?? true;
    setSubmitting(true);
    try {
      await login(data.email, data.password, persistent);
      window.location.href = "/";
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        toast.error("Invalid credentials");
      } else {
        toast.error("Network error. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      className="mt-6 grid gap-6"
      noValidate
      onSubmit={handleSubmit(onSubmit)}
    >
      <label className="grid gap-2" htmlFor={emailId}>
        <span className="text-muted-foreground text-sm leading-none font-medium">
          Email
        </span>
        <input
          id={emailId}
          type="email"
          autoComplete="email"
          inputMode="email"
          placeholder="radiology.team@hospital.org"
          aria-describedby={errors.email ? `${emailId}-error` : undefined}
          aria-invalid={Boolean(errors.email)}
          spellCheck={false}
          className={cn(
            "border-input bg-card text-foreground w-full rounded-[6px] border px-5 py-5 text-base leading-[1.5] transition-[border-color,background-color,color] duration-150 placeholder:text-[var(--color-opencode-mid-gray)] focus-visible:border-[var(--color-opencode-accent-blue)] disabled:cursor-not-allowed disabled:opacity-50",
            errors.email && "border-[var(--color-opencode-danger)]",
          )}
          {...register("email")}
        />
        {errors.email && (
          <span
            id={`${emailId}-error`}
            className="text-sm leading-6 font-medium text-[var(--color-opencode-danger)]"
          >
            {errors.email.message}
          </span>
        )}
      </label>

      <label className="grid gap-2" htmlFor={passwordId}>
        <span className="text-muted-foreground text-sm leading-none font-medium">
          Password
        </span>
        <input
          id={passwordId}
          type="password"
          autoComplete="current-password"
          placeholder="Enter your password"
          aria-describedby={errors.password ? `${passwordId}-error` : undefined}
          aria-invalid={Boolean(errors.password)}
          className={cn(
            "border-input bg-card text-foreground w-full rounded-[6px] border px-5 py-5 text-base leading-[1.5] transition-[border-color,background-color,color] duration-150 placeholder:text-[var(--color-opencode-mid-gray)] focus-visible:border-[var(--color-opencode-accent-blue)] disabled:cursor-not-allowed disabled:opacity-50",
            errors.password && "border-[var(--color-opencode-danger)]",
          )}
          {...register("password")}
        />
        {errors.password && (
          <span
            id={`${passwordId}-error`}
            className="text-sm leading-6 font-medium text-[var(--color-opencode-danger)]"
          >
            {errors.password.message}
          </span>
        )}
      </label>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <label
          className="text-muted-foreground flex items-start gap-3 text-sm leading-[1.5] font-medium"
          htmlFor={persistentId}
        >
          <input
            id={persistentId}
            ref={persistentRef}
            type="checkbox"
            defaultChecked
            className="mt-0.5 size-4 shrink-0 accent-[var(--color-opencode-accent-blue)]"
          />
          <span>Keep this workstation signed in for the shift</span>
        </label>
        <a className="text-sm font-medium" href="/register">
          Need an account?
        </a>
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="bg-primary text-primary-foreground inline-flex min-h-11 w-full items-center justify-center rounded-[4px] px-5 py-2 text-base leading-[1.5] font-medium transition-[background-color,color] duration-150 hover:bg-[var(--color-opencode-mid-gray)] active:bg-[var(--color-opencode-border-outline)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Signing in..." : "Log in to workspace"}
      </button>
    </form>
  );
}
