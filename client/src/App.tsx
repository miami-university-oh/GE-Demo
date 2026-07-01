import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import Login from "@/pages/Login";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Home from "./pages/Home";
import UR5eDashboard from "./pages/UR5eDashboard";

/**
 * Renders the app's route tree via wouter's Switch.
 * Maps `/` → Home, `/ur5e` → UR5eDashboard, and catch-all → NotFound.
 */
function Router() {
  return (
    <Switch>
      <Route path={"/"} component={Home} />
      <Route path={"/ur5e"} component={UR5eDashboard} />
      <Route path={"/404"} component={NotFound} />
      <Route component={NotFound} />
    </Switch>
  );
}

/**
 * Guards the route tree behind authentication.
 * Reads `authenticated` from AuthContext and renders Login when the user
 * is unauthenticated; otherwise renders Router.
 */
function AuthGate() {
  const { authenticated } = useAuth();
  return authenticated ? <Router /> : <Login />;
}

/**
 * Root application component.
 * Wraps the component tree in ErrorBoundary, ThemeProvider (dark),
 * AuthProvider, TooltipProvider, and Toaster before rendering AuthGate.
 */
function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark">
        <AuthProvider>
          <TooltipProvider>
            <Toaster />
            <AuthGate />
          </TooltipProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
