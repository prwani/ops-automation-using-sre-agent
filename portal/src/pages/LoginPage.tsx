import { Button, Card, Text, makeStyles, tokens } from '@fluentui/react-components'
import { useMsal } from '@azure/msal-react'
import { loginRequest } from '../auth/msalConfig'

const useStyles = makeStyles({
  root: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    backgroundColor: tokens.colorNeutralBackground2,
  },
  card: {
    padding: '48px',
    textAlign: 'center',
    maxWidth: '400px',
    width: '100%',
  },
  title: {
    fontSize: '24px',
    fontWeight: '700',
    marginBottom: '8px',
    display: 'block',
  },
  subtitle: {
    color: tokens.colorNeutralForeground2,
    marginBottom: '32px',
    display: 'block',
  },
})

export function LoginPage() {
  const styles = useStyles()
  const { instance } = useMsal()

  return (
    <div className={styles.root}>
      <Card className={styles.card}>
        <Text className={styles.title}>⚙ Ops Automation Portal</Text>
        <Text className={styles.subtitle}>Wintel Operations — sign in with your Microsoft account</Text>
        <Button
          appearance="primary"
          size="large"
          onClick={() => instance.loginPopup(loginRequest)}
        >
          Sign in with Microsoft
        </Button>
      </Card>
    </div>
  )
}
