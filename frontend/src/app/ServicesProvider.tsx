import {
  createContext,
  useContext,
  useEffect,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserServices } from "./BrowserServices";

const Services = createContext<BrowserServices | null>(null);
export function ServicesProvider({
  services,
  children,
}: {
  services: BrowserServices;
  children: ReactNode;
}) {
  useEffect(() => {
    services.start(window);
    return () => services.stop();
  }, [services]);
  return (
    <Services.Provider value={services}>
      <QueryClientProvider client={services.queries.client}>
        {children}
      </QueryClientProvider>
    </Services.Provider>
  );
}
export function useServices() {
  const services = useContext(Services);
  if (!services) throw new Error("Browser services are missing.");
  return services;
}
export function useIdentity() {
  const services = useServices();
  return useSyncExternalStore(services.subscribe, services.getSnapshot);
}
