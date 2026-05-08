import { NextResponse } from "next/server";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function GET() {
  try {
    const response = await fetch(`${apiBaseUrl}/health`, { cache: "no-store" });
    return NextResponse.json({ online: response.ok }, { status: 200 });
  } catch {
    return NextResponse.json({ online: false }, { status: 200 });
  }
}
