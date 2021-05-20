import AMProject from 0x4263f3e1effb2e48

// This transaction allows the Minter account to mint an NFT
// and deposit it into its collection.

transaction(updateId: UInt64, newMetadata: String) {

    // let myProject: @AMProject.Project
    let collectionRef: &AMProject.Collection

    prepare(acct: AuthAccount) {
        // Get the owner's collection capability and borrow a reference
        self.collectionRef = acct.borrow<&AMProject.Collection>(from: /storage/ProjectCollection)
            ?? panic("couldn't borrow collection reference")
        // self.myProject <- self.collectionRef.withdraw(withdrawID: 1)
    }

    execute {
        // Use the minter reference to mint an NFT, which deposits
        // the NFT into the collection that is sent as a parameter.

        // let newMetadata : {String : String} = {
        //     "owners":
        //         "steve, joe, peter, stephane",
        //     "uri": "another URL"
        // }

        self.collectionRef.updateMetadata(id: updateId, metadata: newMetadata)
    }
}