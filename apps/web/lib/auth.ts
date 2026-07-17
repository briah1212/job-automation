import { NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

/**
 * Decode the `sub` claim (user id) out of a JWT without verifying it.
 * The token was just issued by our own backend over a trusted connection,
 * so verification isn't necessary here - we only need the payload.
 */
function decodeUserIdFromToken(token: string): string | undefined {
  try {
    const payload = token.split('.')[1]
    const json = Buffer.from(payload, 'base64').toString('utf-8')
    const decoded = JSON.parse(json)
    return decoded.sub
  } catch {
    return undefined
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' }
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null
        }

        try {
          const res = await fetch(`${process.env.API_URL || 'http://api:8000'}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
              username: credentials.email,
              password: credentials.password,
            }).toString(),
          })

          if (!res.ok) return null

          const data = await res.json()
          const accessToken: string = data.access_token
          if (!accessToken) return null

          const id = decodeUserIdFromToken(accessToken) || credentials.email

          return {
            id,
            email: credentials.email,
            accessToken,
          }
        } catch (error) {
          return null
        }
      }
    })
  ],
  pages: {
    signIn: '/auth/login',
  },
  session: {
    strategy: 'jwt',
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id
        token.accessToken = user.accessToken
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string
      }
      session.accessToken = token.accessToken as string
      return session
    },
  },
}
