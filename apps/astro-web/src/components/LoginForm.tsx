import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { useAuthContext } from "@/lib/auth";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";

const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginForm() {
  const { login } = useAuthContext();
  const [submitting, setSubmitting] = useState(false);
  const persistentRef = useRef<HTMLInputElement>(null);

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
    <form className="auth-form" onSubmit={handleSubmit(onSubmit)}>
      <label>
        <span>Email</span>
        <input
          type="email"
          placeholder="radiology.team@hospital.org"
          {...register("email")}
        />
        {errors.email && (
          <span className="field-error">{errors.email.message}</span>
        )}
      </label>

      <label>
        <span>Password</span>
        <input
          type="password"
          placeholder="Enter your password"
          {...register("password")}
        />
        {errors.password && (
          <span className="field-error">{errors.password.message}</span>
        )}
      </label>

      <div className="form-footer">
        <label className="checkbox">
          <input ref={persistentRef} type="checkbox" defaultChecked />
          <span>Keep this workstation signed in for the shift</span>
        </label>
        <a href="/register">Need an account?</a>
      </div>

      <button type="submit" disabled={submitting}>
        {submitting ? "Signing in…" : "Log in to workspace"}
      </button>
    </form>
  );
}
