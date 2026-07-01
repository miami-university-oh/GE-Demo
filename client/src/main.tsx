import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

/** Mounts the React application into the `#root` DOM element. */
createRoot(document.getElementById("root")!).render(<App />);
