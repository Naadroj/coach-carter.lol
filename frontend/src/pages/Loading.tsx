import styles from './Loading.module.css'

export default function LoadingPage() {
  return (
    <div className={styles.container}>
      <div className={styles.logo}>AMOKK</div>
      <div className={styles.spinner} />
      <p className={styles.tagline}>Votre compagnon ultime pour dominer League of Legends</p>
    </div>
  )
}
