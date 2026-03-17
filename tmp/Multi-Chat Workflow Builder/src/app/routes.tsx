import { createBrowserRouter } from "react-router";
import { MainLayout } from "./components/MainLayout";
import { WorkflowPage } from "./components/WorkflowPage";
import { SettingsPage } from "./components/SettingsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: MainLayout,
    children: [
      { index: true, Component: WorkflowPage },
      { path: "settings", Component: SettingsPage },
    ],
  },
]);
