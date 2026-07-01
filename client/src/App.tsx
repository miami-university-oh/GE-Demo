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

function AuthGate() {
  const { authenticated } = useAuth();
  return authenticated ? <Router /> : <Login />;
}

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
