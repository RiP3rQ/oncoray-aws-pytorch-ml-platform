import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { AuthProvider } from "@/hooks/useAuth";
import { useAuthContext } from "@/lib/auth";
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
    <form className="register-form" onSubmit={handleSubmit(onSubmit)}>
      <label>
        <span>Email</span>
        <input
          type="email"
          placeholder="radiology.ops@clinic.org"
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
          placeholder="Create a strong password"
          {...register("password")}
        />
        {errors.password && (
          <span className="field-error">{errors.password.message}</span>
        )}
      </label>

      <button type="submit" disabled={submitting}>
        {submitting ? "Creating account…" : "Create workspace account"}
      </button>

      <div className="footnote">
        <span>Already onboarded?</span>
        <a href="/login">Log in instead</a>
      </div>
    </form>
  );
}
