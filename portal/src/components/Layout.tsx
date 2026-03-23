import { type ReactNode } from 'react'
import {
  makeStyles,
  tokens,
  Text,
  Button,
} from '@fluentui/react-components'
import {
  GridRegular,
  HistoryRegular,
  ChatRegular,
  BrainCircuitRegular,
  SignOutRegular,
} from '@fluentui/react-icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useMsal } from '@azure/msal-react'

const useStyles = makeStyles({
  root: {
    display: 'flex',
    height: '100vh',
    overflow: 'hidden',
  },
  sidebar: {
    width: '220px',
    backgroundColor: tokens.colorBrandBackground,
    display: 'flex',
    flexDirection: 'column',
    padding: '16px 0',
  },
  sidebarTitle: {
    color: tokens.colorNeutralForegroundOnBrand,
    padding: '0 16px 24px',
    fontWeight: '700',
    fontSize: '16px',
  },
  navButton: {
    justifyContent: 'flex-start',
    color: tokens.colorNeutralForegroundOnBrand,
    width: '100%',
    borderRadius: '0',
    padding: '10px 16px',
    ':hover': {
      backgroundColor: tokens.colorBrandBackgroundHover,
    },
  },
  navButtonActive: {
    backgroundColor: tokens.colorBrandBackgroundPressed,
  },
  main: {
    flex: 1,
    overflow: 'auto',
    backgroundColor: tokens.colorNeutralBackground1,
  },
  spacer: {
    flex: 1,
  },
})

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: <GridRegular /> },
  { path: '/history', label: 'History', icon: <HistoryRegular /> },
  { path: '/chat', label: 'AI Chat', icon: <ChatRegular /> },
  { path: '/memories', label: 'Memories', icon: <BrainCircuitRegular /> },
]

export function Layout({ children }: { children: ReactNode }) {
  const styles = useStyles()
  const navigate = useNavigate()
  const location = useLocation()
  const { instance } = useMsal()

  return (
    <div className={styles.root}>
      <nav className={styles.sidebar}>
        <Text className={styles.sidebarTitle}>⚙ Ops Portal</Text>
        {navItems.map((item) => (
          <Button
            key={item.path}
            appearance="transparent"
            icon={item.icon}
            className={`${styles.navButton} ${location.pathname === item.path ? styles.navButtonActive : ''}`}
            onClick={() => navigate(item.path)}
          >
            {item.label}
          </Button>
        ))}
        <div className={styles.spacer} />
        <Button
          appearance="transparent"
          icon={<SignOutRegular />}
          className={styles.navButton}
          onClick={() => instance.logoutPopup()}
        >
          Sign Out
        </Button>
      </nav>
      <main className={styles.main}>{children}</main>
    </div>
  )
}
