import { useNavigate } from "react-router-dom";

import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DEMO_EMAIL, DEMO_PASSWORD, signIn } from "@/lib/demoAuth";

export default function SignUpPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-dvh bg-bg">
      <div className="mx-auto flex w-full max-w-sm flex-col gap-10 px-5 py-16">
        <div className="flex items-center justify-between">
          <span className="text-lg font-semibold tracking-tight">
            Career<span className="text-accent">OS</span>
          </span>
          <ThemeToggle />
        </div>

        <Card className="space-y-4">
          <CardTitle>Sign up</CardTitle>
          <CardDescription>
            This is a demo build — use the pre-filled demo account below.
          </CardDescription>

          <div className="space-y-3">
            <div>
              <label
                className="mb-1.5 block text-xs font-medium text-text-secondary"
                htmlFor="signup-email"
              >
                Email
              </label>
              <Input id="signup-email" type="email" value={DEMO_EMAIL} readOnly />
            </div>
            <div>
              <label
                className="mb-1.5 block text-xs font-medium text-text-secondary"
                htmlFor="signup-password"
              >
                Password
              </label>
              <Input id="signup-password" type="password" value={DEMO_PASSWORD} readOnly />
              <p className="mt-1.5 text-xs text-text-muted">Demo password: {DEMO_PASSWORD}</p>
            </div>
          </div>

          <Button
            className="w-full"
            onClick={() => {
              signIn();
              navigate("/");
            }}
          >
            Sign up
          </Button>
        </Card>
      </div>
    </div>
  );
}
