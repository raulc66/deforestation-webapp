import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Trees, ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { register } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const fromDemo = searchParams.get("from") === "demo";

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const res = await register({ email, password, name });
    setLoading(false);
    if (res.ok) {
      toast.success(`Welcome, ${res.user.name}`);
      navigate("/trial/setup", { replace: true });
    } else {
      setError(res.error);
    }
  };

  return (
    <div className="auth-shell min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2.5 mb-10">
          <div className="w-10 h-10 rounded-md bg-[#2d5a27] flex items-center justify-center">
            <Trees className="w-5 h-5 text-white" strokeWidth={1.7} />
          </div>
          <div>
            <div className="font-bold text-base">ForestWatch</div>
            <div className="text-[10px] tracking-[0.22em] uppercase text-[#7b827b]">
              Create an account
            </div>
          </div>
        </div>

        <h2 className="text-3xl font-bold tracking-tight mb-2">Start a 14-day trial</h2>
        <p className="text-[#4a524a] mb-8" data-testid="register-intro">
          {fromDemo
            ? "Create a free trial organization to continue with your own monitored areas. This leaves demonstration data and starts a 14-day trial workspace for your account."
            : "Create an account to monitor forests for your organization. After registration you will name the organization and add a forest to watch."}
        </p>

        <form onSubmit={onSubmit} className="space-y-5" data-testid="register-form">
          <div className="space-y-2">
            <Label htmlFor="name">Full name</Label>
            <Input
              id="name"
              data-testid="register-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Forrester"
              required
              className="bg-white border-[#eaece6] h-11"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              data-testid="register-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="bg-white border-[#eaece6] h-11"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password (min 6 characters)</Label>
            <Input
              id="password"
              data-testid="register-password"
              type="password"
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="bg-white border-[#eaece6] h-11"
            />
          </div>

          {error && (
            <div
              data-testid="register-error"
              className="text-sm text-[#9b2226] bg-[#9b2226]/8 border border-[#9b2226]/20 rounded-md px-3 py-2"
            >
              {error}
            </div>
          )}

          <Button
            type="submit"
            data-testid="register-submit"
            disabled={loading}
            className="w-full h-11 bg-[#2d5a27] hover:bg-[#21421d] text-white font-medium"
          >
            {loading ? "Creating account…" : "Create account"}
            <ArrowRight className="w-4 h-4 ml-2" strokeWidth={1.7} />
          </Button>
        </form>

        <div className="mt-8 text-sm text-[#4a524a]">
          Already have an account?{" "}
          <Link
            to="/login"
            data-testid="goto-login"
            className="text-[#2d5a27] font-semibold hover:underline"
          >
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
