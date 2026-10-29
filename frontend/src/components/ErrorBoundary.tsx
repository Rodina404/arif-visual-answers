import { Component, type ReactNode } from 'react'

/** A renderer bug must cost one visual, not the whole answer. */
export class ErrorBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: unknown) {
    console.error('component render failed', error)
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}
