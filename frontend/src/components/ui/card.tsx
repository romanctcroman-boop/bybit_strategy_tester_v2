import React from 'react';

export function Card({
  className = '',
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={`rounded-lg border bg-white shadow-sm ${className}`}>{children}</div>;
}

export function CardHeader({
  className = '',
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={`border-b px-4 py-3 ${className}`}>{children}</div>;
}

export function CardTitle({
  className = '',
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <h3 className={`font-semibold leading-none tracking-tight ${className}`}>{children}</h3>;
}

export function CardContent({
  className = '',
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={`px-4 py-4 ${className}`}>{children}</div>;
}
