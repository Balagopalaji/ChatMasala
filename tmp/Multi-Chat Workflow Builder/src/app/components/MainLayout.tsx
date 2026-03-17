import { Outlet, Link, useLocation } from "react-router";
import { Settings } from "lucide-react";
import { Button } from "./ui/button";
import { Toaster } from "./ui/sonner";

export function MainLayout() {
  const location = useLocation();
  const isSettings = location.pathname === '/settings';

  return (
    <div className="h-screen flex flex-col bg-background">
      <header className="border-b px-4 py-3 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <h1 className="font-semibold">CLI Chat Workflow</h1>
        </Link>
        <Link to={isSettings ? "/" : "/settings"}>
          <Button variant={isSettings ? "default" : "ghost"} size="sm">
            <Settings className="size-4 mr-2" />
            {isSettings ? "Back to Workflow" : "Settings"}
          </Button>
        </Link>
      </header>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
      <Toaster />
    </div>
  );
}