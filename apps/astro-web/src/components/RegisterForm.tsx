import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { AuthProvider } from "@/hooks/useAuth";
import { useAuthContext } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";

const registerSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .max(128, "Password must be at most 128 characters"),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function RegisterForm() {
  return (
    <AuthProvider>
      <RegisterFormInner />
    </AuthProvider>
  );
}

function RegisterFormInner() {
  const { register: registerUser } = useAuthContext();
  const [submitting, setSubmitting] = useState(false);
  const emailId = useId();
  const passwordId = useId();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: standardSchemaResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormValues) => {
    setSubmitting(true);
    try {
      await registerUser(data.email, data.password);
      toast.success("Verification email sent. Check your inbox.");
      window.location.href = "/login";
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Email already registered");
      } else if (err instanceof ApiError && err.status === 401) {
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
          placeholder="radiology.ops@clinic.org"
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
          autoComplete="new-password"
          placeholder="Create a strong password"
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

      <button
        type="submit"
        disabled={submitting}
        className="bg-primary text-primary-foreground inline-flex min-h-11 w-full items-center justify-center rounded-[4px] px-5 py-2 text-base leading-[1.5] font-medium transition-[background-color,color] duration-150 hover:bg-[var(--color-opencode-mid-gray)] active:bg-[var(--color-opencode-border-outline)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Creating account..." : "Create workspace account"}
      </button>

      <div className="text-muted-foreground flex flex-col gap-2 text-sm leading-[1.5] sm:flex-row sm:items-center">
        <span>Already onboarded?</span>
        <a className="font-medium" href="/login">
          Log in instead
        </a>
      </div>
    </form>
  );
}
