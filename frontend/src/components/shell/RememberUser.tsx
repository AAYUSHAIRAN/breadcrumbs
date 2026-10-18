"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { setLogin } from "@/lib/session";

export function RememberUser() {
  const { login } = useParams<{ login: string }>();
  const router = useRouter();
  useEffect(() => {
    setLogin(decodeURIComponent(login));
    router.replace("/home");
  }, [login, router]);
  return null;
}
