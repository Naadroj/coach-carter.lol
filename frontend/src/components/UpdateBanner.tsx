import styles from './UpdateBanner.module.css'

export default function UpdateBanner() {
  const install = () => window.electronAPI?.installUpdate()
  return (
    <div className={styles.banner}>
      <span>Une mise à jour est prête.</span>
      <button onClick={install}>Redémarrer et installer</button>
    </div>
  )
}
